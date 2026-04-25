import math
from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Optional
from bson import ObjectId
import os

from app.models.listing import Listing
from app.models.pricing_rule import PricingRule
from app.models.inventory_master import InventoryMaster
from app.models.engine_run import EngineRun
from app.models.benchmark_data import BenchmarkData
from app.engine.waterfall import (
    ListingConfig, Rule, BookingContext, compute_day, date_str
)

# NOTE: AirbticsMarketContext is mocked/simplified here for space, 
# you will need to implement the actual caching logic similarly to TS.

def to_num(val: Any) -> float:
    if val is None: return 0.0
    try: return float(val)
    except: return 0.0

def add_days(dt: date, days: int) -> date:
    return dt + timedelta(days=days)

def date_str_from_date(dt: date) -> str:
    return dt.isoformat()

def average(nums: List[float]) -> float:
    if not nums: return 0.0
    return sum(nums) / len(nums)

def clamp(n: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, n))

def compute_gaps(start_date: date, end_date: date, booking_map: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    gap_map = {}
    total_days = (end_date - start_date).days + 1
    dates = []
    booked = []
    
    for i in range(total_days):
        d = add_days(start_date, i)
        ds = date_str_from_date(d)
        dates.append(ds)
        info = booking_map.get(ds, {})
        booked.append(info.get("isBooked", False))

    i = 0
    while i < total_days:
        if booked[i]:
            i += 1
            continue
        
        gap_start_idx = i
        has_booking_before = gap_start_idx > 0 and booked[gap_start_idx - 1]
        
        while i < total_days and not booked[i]:
            i += 1
            
        gap_end_idx = i - 1
        has_booking_after = i < total_days and booked[i]
        
        if has_booking_before and has_booking_after:
            gap_length = gap_end_idx - gap_start_idx + 1
            gap_info = {
                "gapLength": gap_length,
                "gapStart": dates[gap_start_idx],
                "gapEnd": dates[gap_end_idx]
            }
            for j in range(gap_start_idx, gap_end_idx + 1):
                gap_map[dates[j]] = gap_info
                
    return gap_map

async def run_pipeline(listing_id: str, trigger_detail: Optional[str] = None):
    lid = ObjectId(listing_id)
    started_at = datetime.utcnow()
    
    try:
        listing = await Listing.get(lid)
        if not listing:
            raise Exception(f"Listing {listing_id} not found")

        # 1. Base price resolution
        latest_benchmark = await BenchmarkData.find(
            BenchmarkData.orgId == listing.orgId, 
            BenchmarkData.listingId == lid
        ).sort(-BenchmarkData.createdAt).first_or_none()
        
        hostaway_price = to_num(listing.price)
        one_year_ago = date.today() - timedelta(days=365)
        
        historical_prices = await InventoryMaster.find(
            InventoryMaster.orgId == listing.orgId,
            InventoryMaster.listingId == lid,
            InventoryMaster.date >= date_str_from_date(one_year_ago),
            InventoryMaster.date <= date_str_from_date(date.today()),
            InventoryMaster.currentPrice > 0
        ).project(InventoryMaster.currentPrice).to_list()
        
        history_vals = [float(p.currentPrice) for p in historical_prices if p.currentPrice and p.currentPrice > 0]
        one_year_avg_base = average(history_vals)
        
        b_week = latest_benchmark.recommendedWeekday if latest_benchmark else 0
        b_p50 = latest_benchmark.p50Rate if latest_benchmark else 0
        
        if one_year_avg_base > 0:
            base_price_source = "history_1y"
        elif (b_week and b_week > 0) or (b_p50 and b_p50 > 0):
            base_price_source = "benchmark"
        else:
            base_price_source = "hostaway"
            
        effective_base_price = one_year_avg_base if one_year_avg_base > 0 else (b_week if (b_week and b_week > 0) else (b_p50 if (b_p50 and b_p50 > 0) else hostaway_price))
        
        effective_weekend_base = latest_benchmark.recommendedWeekend if (latest_benchmark and latest_benchmark.recommendedWeekend and latest_benchmark.recommendedWeekend > 0) else 0
        
        listing.basePriceSource = base_price_source
        listing.basePriceLastComputedAt = datetime.utcnow()
        await listing.save()

        lookback_days = listing.occupancyLookbackDays or 30
        current_occupancy_pct = 0.0
        if listing.occupancyEnabled:
            lookback_start = date.today() - timedelta(days=lookback_days)
            lookback_docs = await InventoryMaster.find(
                InventoryMaster.orgId == listing.orgId,
                InventoryMaster.listingId == lid,
                InventoryMaster.date >= date_str_from_date(lookback_start),
                InventoryMaster.date <= date_str_from_date(date.today())
            ).to_list()
            if lookback_docs:
                booked_count = sum(1 for d in lookback_docs if d.status != "available")
                current_occupancy_pct = (booked_count / len(lookback_docs)) * 100.0

        config_args = listing.model_dump()
        config_args['basePrice'] = effective_base_price
        config_args['basePriceWeekend'] = effective_weekend_base
        config_args['currentOccupancyPct'] = current_occupancy_pct
        
        config = ListingConfig(**config_args)

        listing_rules = await PricingRule.find(
            PricingRule.listingId == lid,
            PricingRule.enabled == True,
            PricingRule.scope == "listing"
        ).sort(+PricingRule.priority).to_list()

        all_rules: List[Rule] = []
        for r in listing_rules:
            rd = r.model_dump()
            rd['id'] = str(r.id)
            all_rules.append(Rule(**rd))

        today = date.today()
        end_date = today + timedelta(days=364)
        
        existing_inventory = await InventoryMaster.find(
            InventoryMaster.orgId == listing.orgId,
            InventoryMaster.listingId == lid,
            InventoryMaster.date >= date_str_from_date(today)
        ).sort(+InventoryMaster.date).to_list()

        booking_map = { d.date: {"isBooked": d.status != "available"} for d in existing_inventory }
        gap_map = compute_gaps(today, end_date, booking_map)
        
        days_changed = 0
        
        for i in range(365):
            current_date = add_days(today, i)
            ds = date_str_from_date(current_date)
            booking = booking_map.get(ds, {})
            gap = gap_map.get(ds, {})
            
            yesterday_booked = booking_map.get(date_str_from_date(add_days(current_date, -1)), {}).get("isBooked", False)
            tomorrow_booked = booking_map.get(date_str_from_date(add_days(current_date, 1)), {}).get("isBooked", False)
            
            booking_ctx = BookingContext(
                isBooked=booking.get("isBooked", False),
                gapLength=gap.get("gapLength"),
                gapStart=gap.get("gapStart"),
                gapEnd=gap.get("gapEnd"),
                adjacentToBooking=yesterday_booked or tomorrow_booked
            )
            
            day_config = ListingConfig(**config.__dict__)
            
            result = compute_day(current_date, today, day_config, all_rules, booking_ctx)
            
            # Using Beanie upsert logic (Find and update, if not found then insert)
            inv = await InventoryMaster.find_one(
                InventoryMaster.orgId == listing.orgId,
                InventoryMaster.listingId == lid,
                InventoryMaster.date == ds
            )
            if not inv:
                inv = InventoryMaster(
                    orgId=listing.orgId,
                    listingId=lid,
                    date=ds,
                    currentPrice=effective_base_price
                )
            
            inv.status = "booked" if booking_ctx.isBooked else "available"
            inv.proposedPrice = result.price
            inv.reasoning = result.note
            inv.proposalStatus = "pending"
            inv.minStay = result.minimumStay
            inv.maxStay = result.maximumStay
            inv.closedToArrival = result.closedToArrival == 1
            inv.closedToDeparture = result.closedToDeparture == 1
            
            await inv.save()
            days_changed += 1

        duration_ms = int((datetime.utcnow() - started_at).total_seconds() * 1000)
        await EngineRun(
            orgId=listing.orgId,
            listingId=lid,
            startedAt=started_at,
            status="SUCCESS",
            daysChanged=days_changed,
            durationMs=duration_ms
        ).insert()

    except Exception as e:
        duration_ms = int((datetime.utcnow() - started_at).total_seconds() * 1000)
        listing = await Listing.get(lid)
        await EngineRun(
            orgId=listing.orgId if listing else ObjectId(),
            listingId=lid,
            startedAt=started_at,
            status="FAILED",
            errorMessage=str(e),
            durationMs=duration_ms
        ).insert()
        raise e
