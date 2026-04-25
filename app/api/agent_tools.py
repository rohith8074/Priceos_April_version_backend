"""
agent_tools.py — FastAPI router

Hosts all Lyzr agent tool endpoints that were previously called directly
from the frontend. The frontend now proxies through here, keeping all
LLM, external API, and DB logic server-side.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
from bson import ObjectId

agent_tools_router = APIRouter(prefix="/agent-tools", tags=["agent-tools"])


async def get_listing_context(listing_id: str, org_id: str) -> str:
    """
    Returns a text block with listing profile, rules, and latest stats.
    Used for context injection in both Pricing and Guest Agents.
    """
    try:
        from app.models.listing import Listing
        from app.models.inventory_master import InventoryMaster
        from app.models.reservation import Reservation
        from datetime import datetime, timedelta

        listing = await resolve_listing(org_id, listing_id)
        if not listing:
            return "No listing profile found."

        # Fetch recent stats
        today = datetime.utcnow().strftime("%Y-%m-%d")
        end_date = (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d")
        
        inv_docs = await InventoryMaster.find(
            InventoryMaster.orgId == oid(org_id),
            InventoryMaster.listingId == listing.id,
            InventoryMaster.date >= today,
            InventoryMaster.date <= end_date
        ).to_list()
        
        booked_days = sum(1 for d in inv_docs if d.status == "booked")
        total_days = len(inv_docs)
        occ = round((booked_days / total_days) * 100) if total_days > 0 else 0
        
        context = f"""
PROPERTY PROFILE:
Name: {listing.name}
Area: {listing.area}
City: {listing.city}
Bedrooms: {listing.bedroomsNumber}
Standard Rate: {listing.price} {listing.currencyCode or 'AED'}

RULES & POLICIES:
- Check-in: 3:00 PM
- Check-out: 11:00 AM
- Smoking: No
- Pets: No (unless specified)
- Parties: Strictly Prohibited

CURRENT STATS (Next 30 Days):
- Occupancy: {occ}%
- Booked Days: {booked_days}/{total_days}
- Status: {"Healthy Pacing" if occ > 50 else "Opportunity for Growth"}
"""
        return context.strip()
    except Exception as e:
        print(f"⚠️ [ERROR] Failed to fetch listing context: {e}")
        return f"Listing Details: {listing_id}"




def oid(s: str) -> ObjectId:
    if not s:
        raise HTTPException(status_code=400, detail="Empty ObjectId provided")
    # Clean the string from common LLM artifacts like quotes or spaces
    cleaned = str(s).strip().replace('"', '').replace("'", "")
    try:
        return ObjectId(cleaned)
    except Exception:
        # Log the actual failing value for debugging (visible in server logs)
        print(f"!!! [DEBUG] Invalid ObjectId attempt: '{s}' (cleaned: '{cleaned}')")
        raise HTTPException(status_code=400, detail=f"Invalid ObjectId: '{cleaned}'")


async def resolve_listing(orgId: str, listingId: str):
    from app.models.listing import Listing

    org_oid = oid(orgId)
    listing = None

    try:
        if len(listingId) == 24:
            listing = await Listing.find_one(
                Listing.id == ObjectId(listingId),
                Listing.orgId == org_oid,
            )
    except Exception:
        pass

    if not listing:
        listing = await Listing.find_one(
            Listing.hostawayId == str(listingId),
            Listing.orgId == org_oid,
        )

    if not listing:
        raise HTTPException(status_code=404, detail=f"Listing not found for ID: {listingId}")

    return listing


# ── Portfolio ──────────────────────────────────────────────────────────────────

@agent_tools_router.get("/portfolio-overview")
async def portfolio_overview(orgId: str, dateFrom: str, dateTo: str):
    from app.models.listing import Listing
    from app.models.inventory_master import InventoryMaster
    import asyncio

    org_oid = oid(orgId)
    listings, inv_agg = await asyncio.gather(
        Listing.find(Listing.orgId == org_oid, Listing.isActive == True).to_list(),
        InventoryMaster.find(
            InventoryMaster.orgId == org_oid,
            InventoryMaster.date >= dateFrom,
            InventoryMaster.date <= dateTo
        ).to_list()
    )

    stat_map: dict = {}
    for doc in inv_agg:
        lid = str(doc.listingId)
        s = stat_map.setdefault(lid, {"totalDays": 0, "bookedDays": 0, "blockedDays": 0, "revenue": 0.0, "prices": []})
        s["totalDays"] += 1
        if doc.status == "booked":
            s["bookedDays"] += 1
            s["revenue"] += float(doc.currentPrice or 0)
        if doc.status == "blocked":
            s["blockedDays"] += 1
        if doc.currentPrice:
            s["prices"].append(float(doc.currentPrice))

    properties = []
    for listing in listings:
        s = stat_map.get(str(listing.id), {})
        total = s.get("totalDays", 0)
        blocked = s.get("blockedDays", 0)
        booked = s.get("bookedDays", 0)
        bookable = max(total - blocked, 0)
        occ = round((booked / bookable) * 100) if bookable > 0 else 0
        prices = s.get("prices", [])
        avg_rate = round(sum(prices) / len(prices)) if prices else int(listing.price or 0)
        rev = round(s.get("revenue", 0), 2)
        properties.append({
            "listingId": str(listing.id),
            "name": listing.name,
            "occupancyPct": occ,
            "revenue": rev,
            "avgNightlyRate": avg_rate
        })

    total_revenue = round(sum(p["revenue"] for p in properties), 2)
    avg_occ = round(sum(p["occupancyPct"] for p in properties) / len(properties)) if properties else 0
    avg_nightly = round(sum(p["avgNightlyRate"] for p in properties) / len(properties)) if properties else 0

    return {
        "totalProperties": len(properties),
        "avgOccupancyPct": avg_occ,
        "totalRevenue": total_revenue,
        "avgNightlyRate": avg_nightly,
        "properties": properties
    }


@agent_tools_router.get("/revenue-snapshot")
async def revenue_snapshot(orgId: str, dateFrom: str, dateTo: str, groupBy: str = "day"):
    from app.models.reservation import Reservation
    from app.models.listing import Listing
    import asyncio

    org_oid = oid(orgId)
    reservations = await Reservation.find(
        Reservation.orgId == org_oid,
        Reservation.checkIn <= dateTo,
        Reservation.checkOut >= dateFrom
    ).to_list()

    total_rev = round(sum(float(r.totalPrice or 0) for r in reservations), 2)
    count = len(reservations)
    avg_val = round(total_rev / count, 2) if count else 0

    totals = {"revenue": total_rev, "bookings": count, "avgBookingValue": avg_val}

    breakdown = []
    if groupBy == "property":
        listings = await Listing.find(Listing.orgId == org_oid).to_list()
        listing_map = {str(l.id): l.name for l in listings}
        grouped: dict = {}
        for r in reservations:
            key = str(r.listingId)
            g = grouped.setdefault(key, {"revenue": 0.0, "bookings": 0})
            g["revenue"] += float(r.totalPrice or 0)
            g["bookings"] += 1
        breakdown = [{"listingId": k, "name": listing_map.get(k, "Unknown"), "revenue": round(v["revenue"], 2), "bookings": v["bookings"]} for k, v in grouped.items()]
    else:
        grouped_dates: dict = {}
        for r in reservations:
            key = r.checkIn[:10] if r.checkIn else "unknown"
            g = grouped_dates.setdefault(key, {"revenue": 0.0, "bookings": 0})
            g["revenue"] += float(r.totalPrice or 0)
            g["bookings"] += 1
        breakdown = [{"date": k, "revenue": round(v["revenue"], 2), "bookings": v["bookings"]} for k, v in sorted(grouped_dates.items())]

    return {"totals": totals, "breakdown": breakdown}


@agent_tools_router.get("/system-status")
async def system_status(orgId: str):
    from app.models.engine_run import EngineRun
    from app.models.inventory_master import InventoryMaster
    from app.models.insight import Insight
    import asyncio

    org_oid = oid(orgId)
    cutoff = datetime.utcnow() - timedelta(hours=24)

    last_run, pending, approved_24h, critical = await asyncio.gather(
        EngineRun.find(EngineRun.orgId == org_oid).sort(-EngineRun.startedAt).first_or_none(),
        InventoryMaster.find(InventoryMaster.orgId == org_oid, InventoryMaster.proposalStatus == "pending").count(),
        InventoryMaster.find(InventoryMaster.orgId == org_oid, InventoryMaster.proposalStatus == "approved", InventoryMaster.updatedAt >= cutoff).count(),
        Insight.find(Insight.orgId == org_oid, Insight.severity == "high", Insight.status == "pending").count()
    )

    last_run_status = last_run.status if last_run else "never_run"
    last_run_at = last_run.startedAt.isoformat() if last_run else None
    age_sec = int((datetime.utcnow() - last_run.startedAt).total_seconds()) if last_run else None
    is_stale = age_sec is not None and age_sec > 4 * 3600

    system_state = ("error" if last_run_status == "FAILED" else
                    "observing" if is_stale else
                    "paused" if critical > 0 else
                    "connected" if last_run_status == "never_run" else "active")

    return {
        "systemState": system_state,
        "summary": {
            "pendingProposals": pending,
            "criticalInsights": critical,
            "isStale": is_stale,
            "lastRunAt": last_run_at,
            "lastRunStatus": last_run_status,
        }
    }


# ── Property ───────────────────────────────────────────────────────────────────

@agent_tools_router.get("/property-profile")
async def property_profile(orgId: str, listingId: str):
    listing = await resolve_listing(orgId, listingId)

    return {
        "listingId": str(listing.id), "name": listing.name, "area": listing.area,
        "city": listing.city, "bedrooms": listing.bedroomsNumber,
        "basePrice": float(listing.price or 0), "priceFloor": float(listing.priceFloor or 0),
        "priceCeiling": float(listing.priceCeiling or 0),
        "hostawayId": listing.hostawayId
    }

@agent_tools_router.get("/v1/get-property-profile")
async def get_property_profile_v1(orgId: str, listingId: str, apiKey: Optional[str] = None):
    return await property_profile(orgId, listingId)


@agent_tools_router.get("/calendar-metrics")
async def calendar_metrics(orgId: str, listingId: str, dateFrom: str, dateTo: str):
    from app.models.inventory_master import InventoryMaster

    org_oid = oid(orgId)
    listing = await resolve_listing(orgId, listingId)

    docs = await InventoryMaster.find(
        InventoryMaster.orgId == org_oid, InventoryMaster.listingId == listing.id,
        InventoryMaster.date >= dateFrom, InventoryMaster.date <= dateTo
    ).to_list()
    total = len(docs)
    booked = sum(1 for d in docs if d.status == "booked")
    blocked = sum(1 for d in docs if d.status == "blocked")
    bookable = max(total - blocked, 0)
    prices = [float(d.currentPrice) for d in docs if d.currentPrice]
    return {
        "totalDays": total, "bookedDays": booked, "blockedDays": blocked, "bookableDays": bookable,
        "occupancyPct": round((booked / bookable) * 100, 1) if bookable > 0 else 0,
        "avgNightlyRate": round(sum(prices) / len(prices), 2) if prices else 0,
        "totalRevenue": round(sum(float(d.currentPrice or 0) for d in docs if d.status == "booked"), 2)
    }


@agent_tools_router.get("/v1/get-property-calendar-metrics")
async def get_property_calendar_metrics_v1(
    orgId: str,
    listingId: str,
    dateFrom: str,
    dateTo: str,
    apiKey: Optional[str] = None,
):
    return await calendar_metrics(orgId, listingId, dateFrom, dateTo)


@agent_tools_router.get("/property-reservations")
async def property_reservations(orgId: str, listingId: str, dateFrom: str, dateTo: str, limit: int = 50):
    from app.models.reservation import Reservation

    listing = await resolve_listing(orgId, listingId)

    docs = await Reservation.find(
        Reservation.orgId == oid(orgId), Reservation.listingId == listing.id,
        Reservation.checkIn <= dateTo, Reservation.checkOut >= dateFrom
    ).sort(+Reservation.checkIn).limit(limit).to_list()
    return {"count": len(docs), "reservations": [
        {"guestName": r.guestName, "channel": r.channelName, "checkIn": r.checkIn,
         "checkOut": r.checkOut, "nights": r.nights, "totalPrice": float(r.totalPrice or 0), "status": r.status}
        for r in docs
    ]}


@agent_tools_router.get("/v1/get-property-reservations")
async def get_property_reservations_v1(
    orgId: str,
    listingId: str,
    dateFrom: str,
    dateTo: str,
    limit: int = 50,
    apiKey: Optional[str] = None,
):
    return await property_reservations(orgId, listingId, dateFrom, dateTo, limit)


@agent_tools_router.get("/market-events")
async def market_events(orgId: str, dateFrom: str, dateTo: str, listingId: Optional[str] = None):
    from app.models.market_event import MarketEvent
    from app.services.market_intelligence import sync_external_market_intelligence
    
    org_oid = oid(orgId)
    
    # 1. Try DB first
    docs = await MarketEvent.find(
        MarketEvent.orgId == org_oid, MarketEvent.isActive == True,
        MarketEvent.endDate >= dateFrom, MarketEvent.startDate <= dateTo
    ).sort(+MarketEvent.startDate).to_list()
    
    # 2. If DB is empty, trigger Agent 6 internet search
    if not docs:
        print(f"    [AGENT TOOL] No events in DB for {dateFrom}. Triggering Agent 6...")
        
        # Get city/area from listing or org
        city = "Dubai"
        area = ""
        if listingId:
            listing = await resolve_listing(orgId, listingId)
            city = listing.city or "Dubai"
            area = listing.area or ""
        
        await sync_external_market_intelligence(
            org_id=org_oid,
            city=city,
            area=area,
            date_from=dateFrom,
            date_to=dateTo
        )
        
        # Re-fetch from DB
        docs = await MarketEvent.find(
            MarketEvent.orgId == org_oid, MarketEvent.isActive == True,
            MarketEvent.endDate >= dateFrom, MarketEvent.startDate <= dateTo
        ).sort(+MarketEvent.startDate).to_list()

    return {"count": len(docs), "events": [
        {"name": e.name, "startDate": e.startDate, "endDate": e.endDate,
         "impactLevel": e.impactLevel, "upliftPct": float(e.upliftPct or 0),
         "description": e.description, "source": e.source}
        for e in docs
    ]}


@agent_tools_router.get("/v1/get-property-market-events")
async def get_property_market_events_v1(
    orgId: str,
    dateFrom: str,
    dateTo: str,
    listingId: Optional[str] = None,
    apiKey: Optional[str] = None,
):
    return await market_events(orgId, dateFrom, dateTo, listingId)


@agent_tools_router.get("/benchmark")
async def get_benchmark(orgId: str, listingId: str, dateFrom: str, dateTo: str,
                        bedrooms: int = 1, marketId: str = "2286"):
    """
    Cache-first benchmark.
    1. Check AirbticsCache for comp_listings:{marketId}:{bedrooms}br
    2. Fall back to BenchmarkData collection
    3. If both miss, trigger Agent 7 internet research fallback
    """
    from app.models.airbtics_cache import AirbticsCache
    from app.models.benchmark_data import BenchmarkData
    from app.services.market_intelligence import sync_internet_benchmark
    from datetime import datetime, timezone

    org_oid = oid(orgId)
    listing = await resolve_listing(orgId, listingId)
    listing_oid = listing.id

    cache_key = f"comp_listings:{marketId}:{bedrooms}br"
    cache = await AirbticsCache.find_one(
        AirbticsCache.cacheKey == cache_key,
        AirbticsCache.expiresAt > datetime.now(timezone.utc)
    )

    if cache:
        d = cache.data
        return {
            "source":       "cache",
            "cache_key":    cache_key,
            "cache_available": True,
            "compCount":    d.get("compCount", 0),
            "p25":          d.get("p25Adr"),
            "p50":          d.get("p50Adr"),
            "p75":          d.get("p75Adr"),
            "p90":          d.get("p90Adr"),
            "avgAdr":       d.get("avgAdr"),
            "avgOccupancy": d.get("avgOccupancy"),
            "comps":        d.get("comps", [])[:15],
            "verdict":      None,
            "recommendedWeekday":  round(d.get("p50Adr", 0) * 0.97, 2) if d.get("p50Adr") else None,
            "recommendedWeekend":  round(d.get("p75Adr", 0) * 0.95, 2) if d.get("p75Adr") else None,
            "recommendedEvent":    round(d.get("p90Adr", 0) * 0.90, 2) if d.get("p90Adr") else None,
            "avgWeekday":          round(d.get("p50Adr", 0) * 1.05, 2) if d.get("p50Adr") else None,
            "avgWeekend":          round(d.get("p75Adr", 0) * 1.10, 2) if d.get("p75Adr") else None,
        }

    # Fallback 1: BenchmarkData written by prior runs
    b = await BenchmarkData.find(
        BenchmarkData.orgId == org_oid, BenchmarkData.listingId == listing_oid
    ).sort(-BenchmarkData.updatedAt).first_or_none()

    if b:
        return {
            "source":          "benchmark_data",
            "cache_available": False,
            "p25":             b.p25Rate, "p50": b.p50Rate, "p75": b.p75Rate,
            "verdict":         b.verdict,
            "comps":           [],
        }

    # Fallback 2: Trigger Agent 7 (Internet Search)
    print(f"    [AGENT TOOL] No benchmark data found. Triggering Agent 7 fallback...")
    if listing:
        agent_res = await sync_internet_benchmark(
            org_id=org_oid,
            listing_id=listing_oid,
            city=listing.city or "Dubai",
            area=listing.area or "Dubai Marina",
            bedrooms=listing.bedroomsNumber or bedrooms,
            date_from=dateFrom,
            date_to=dateTo
        )
        if agent_res.get("success") and agent_res.get("data"):
            d = agent_res["data"]
            dist = d.get("rate_distribution", {})
            return {
                "source": "internet_fallback",
                "cache_available": False,
                "p25": dist.get("p25"),
                "p50": dist.get("p50"),
                "p75": dist.get("p75"),
                "p90": dist.get("p90"),
                "comps": d.get("comps", [])[:10],
                "verdict": d.get("pricing_verdict", {}).get("verdict"),
            }

    return {"source": "none", "cache_available": False, "verdict": None,
            "p25": None, "p50": None, "p75": None}


@agent_tools_router.get("/v1/get-property-benchmark")
async def get_property_benchmark_v1(
    orgId: str,
    listingId: str,
    dateFrom: str,
    dateTo: str,
    apiKey: Optional[str] = None,
):
    return await get_benchmark(orgId, listingId, dateFrom, dateTo)


@agent_tools_router.get("/demand-pacing")
async def get_demand_pacing(dateFrom: str, dateTo: str, marketId: str = "2286"):
    """
    Returns per-date demand pacing from AirbticsCache.
    CRO Router injects this into PropertyAnalyst, PriceGuard, and AnomalyDetector.
    """
    from app.models.airbtics_cache import AirbticsCache
    from datetime import datetime, timezone, timedelta

    # Build list of all dates in range
    try:
        start = datetime.strptime(dateFrom, "%Y-%m-%d")
        end   = datetime.strptime(dateTo,   "%Y-%m-%d")
    except Exception:
        return {"error": "Invalid date format. Use YYYY-MM-DD.", "pacing": []}

    days = []
    cur = start
    while cur <= end:
        days.append(cur.strftime("%Y-%m-%d"))
        cur += timedelta(days=1)

    keys = [f"demand_calendar:{marketId}:{d}" for d in days]
    now  = datetime.now(timezone.utc)

    docs = await AirbticsCache.find(
        {"cacheKey": {"$in": keys}, "expiresAt": {"$gt": now}}
    ).to_list()

    doc_map = {doc.cacheKey: doc.data for doc in docs}

    pacing = []
    for day in days:
        key  = f"demand_calendar:{marketId}:{day}"
        data = doc_map.get(key)
        if data:
            pacing.append({
                "date":        day,
                "demandScore": data.get("demandScore", 0),
                "avgPrice":    data.get("avgPrice", 0),
                "pacing":      data.get("pacing", 0),
                "demandTier":  data.get("demandTier", "low"),
                "dayOfWeek":   data.get("dayOfWeek", ""),
                "isWeekend":   data.get("isWeekend", False),
            })
        else:
            # No cache data for this date — return neutral placeholder
            pacing.append({
                "date":        day,
                "demandScore": None,
                "avgPrice":    None,
                "pacing":      None,
                "demandTier":  "unknown",
                "dayOfWeek":   "",
                "isWeekend":   False,
            })

    cache_hits = sum(1 for p in pacing if p["demandScore"] is not None)
    return {
        "marketId":       marketId,
        "dateFrom":       dateFrom,
        "dateTo":         dateTo,
        "totalDays":      len(pacing),
        "cacheHits":      cache_hits,
        "cacheMisses":    len(pacing) - cache_hits,
        "pacing":         pacing,
    }


@agent_tools_router.get("/market-overview")
async def get_market_overview(month: str, marketId: str = "2286"):
    """
    Returns market-level ADR, RevPAR, occupancy for a given month (YYYY-MM-01).
    Used by BookingIntelligence to benchmark ADR against market, and by AnomalyDetector.
    """
    from app.models.airbtics_cache import AirbticsCache
    from datetime import datetime, timezone

    # Normalise: accept YYYY-MM or YYYY-MM-01
    if len(month) == 7:
        month = month + "-01"

    key = f"market_overview:{marketId}:{month}"
    doc = await AirbticsCache.find_one(
        AirbticsCache.cacheKey == key,
        AirbticsCache.expiresAt > datetime.now(timezone.utc)
    )

    if not doc:
        return {"found": False, "month": month, "marketId": marketId,
                "adr": None, "revpar": None, "occupancyRate": None,
                "activeListings": None, "demandScore": None}

    d = doc.data
    return {
        "found":          True,
        "month":          month,
        "marketId":       marketId,
        "adr":            d.get("adr"),
        "revpar":         d.get("revpar"),
        "occupancyRate":  d.get("occupancyRate"),
        "activeListings": d.get("activeListings"),
        "demandScore":    d.get("demandScore"),
    }


@agent_tools_router.get("/comp-listings")
async def get_comp_listings(bedrooms: int = 1, marketId: str = "2286"):
    """
    Returns the full comp listing array for the given bedroom count.
    Used by Market Setup UI to display real competitor data instead of internet-scraped results.
    """
    from app.models.airbtics_cache import AirbticsCache
    from datetime import datetime, timezone

    key = f"comp_listings:{marketId}:{bedrooms}br"
    doc = await AirbticsCache.find_one(
        AirbticsCache.cacheKey == key,
        AirbticsCache.expiresAt > datetime.now(timezone.utc)
    )

    if not doc:
        return {"found": False, "bedrooms": bedrooms, "marketId": marketId, "comps": []}

    d = doc.data
    return {
        "found":        True,
        "bedrooms":     bedrooms,
        "marketId":     marketId,
        "compCount":    d.get("compCount", 0),
        "p25Adr":       d.get("p25Adr"),
        "p50Adr":       d.get("p50Adr"),
        "p75Adr":       d.get("p75Adr"),
        "p90Adr":       d.get("p90Adr"),
        "avgAdr":       d.get("avgAdr"),
        "avgOccupancy": d.get("avgOccupancy"),
        "comps":        d.get("comps", []),
    }


@agent_tools_router.post("/benchmark/refresh")
async def refresh_benchmark_from_cache(orgId: str, listingId: str,
                                        bedrooms: int = 1, marketId: str = "2286"):
    """
    Reads comp_listings from AirbticsCache and writes/updates a BenchmarkData document
    for the org/listing. Allows bypassing Benchmark Agent's internet search for Dubai.
    """
    from app.models.airbtics_cache import AirbticsCache
    from app.models.benchmark_data import BenchmarkData
    from datetime import datetime, timezone

    key = f"comp_listings:{marketId}:{bedrooms}br"
    doc = await AirbticsCache.find_one(
        AirbticsCache.cacheKey == key,
        AirbticsCache.expiresAt > datetime.now(timezone.utc)
    )
    if not doc:
        return {"refreshed": False, "reason": "No cache data found. Run seed_market_data.py first."}

    d = doc.data
    p50 = d.get("p50Adr") or 0

    # Determine pricing verdict relative to listing's current price
    from app.models.listing import Listing
    listing = await Listing.find_one(Listing.id == oid(listingId), Listing.orgId == oid(orgId))
    current_price = float(listing.price or 0) if listing else 0
    percentile_pos = 0
    if p50 and current_price:
        p25 = d.get("p25Adr", 0) or 0
        p75 = d.get("p75Adr", 0) or 0
        if current_price < p25:
            verdict = "UNDERPRICED"
        elif current_price <= p50 * 1.3:
            verdict = "FAIR"
        elif current_price <= p75:
            verdict = "SLIGHTLY_ABOVE"
        else:
            verdict = "OVERPRICED"
    else:
        verdict = None

    existing = await BenchmarkData.find_one(
        BenchmarkData.orgId == oid(orgId), BenchmarkData.listingId == oid(listingId)
    )
    if existing:
        existing.p25Rate   = d.get("p25Adr")
        existing.p50Rate   = d.get("p50Adr")
        existing.p75Rate   = d.get("p75Adr")
        existing.verdict   = verdict
        existing.updatedAt = datetime.now(timezone.utc)
        await existing.save()
        action = "updated"
    else:
        from bson import ObjectId
        b = BenchmarkData(
            orgId=oid(orgId), listingId=oid(listingId),
            p25Rate=d.get("p25Adr"), p50Rate=d.get("p50Adr"),
            p75Rate=d.get("p75Adr"), verdict=verdict,
        )
        await b.insert()
        action = "created"

    return {
        "refreshed": True, "action": action,
        "p25": d.get("p25Adr"), "p50": d.get("p50Adr"),
        "p75": d.get("p75Adr"), "p90": d.get("p90Adr"),
        "verdict": verdict, "compCount": d.get("compCount", 0),
        "source": "airbtics_cache",
    }


@agent_tools_router.get("/listing-metadata")
async def listing_metadata(orgId: str):
    from app.models.listing import Listing
    listings = await Listing.find(Listing.orgId == oid(orgId), Listing.isActive == True).to_list()
    return {"count": len(listings), "listings": [
        {"listingId": str(l.id), "name": l.name, "area": l.area, "city": l.city}
        for l in listings
    ]}


# ── Chat / Lyzr ────────────────────────────────────────────────────────────────

class SuggestReplyReq(BaseModel):
    guestMessage: str
    guestName: str
    propertyName: Optional[str] = None

@agent_tools_router.post("/suggest-reply")
async def suggest_reply(req: SuggestReplyReq):
    from app.services.lyzr import call_lyzr_agent
    import os
    agent_id = os.environ.get("LYZR_Chat_Response_Agent_ID", "")
    if not agent_id:
        return {"reply": f"Hi {req.guestName}, thanks for reaching out. I'll get back to you shortly.", "source": "fallback"}

    prompt = f'Property: "{req.propertyName or "Our Property"}"\nGuest: {req.guestName}\nMessage: "{req.guestMessage}"\n\nGenerate a professional, warm reply in 2-4 sentences.'
    result = await call_lyzr_agent(agent_id=agent_id, message=prompt)
    if result.ok:
        return {"reply": result.response, "source": "lyzr"}
    return {"reply": f"Hi {req.guestName}, thanks for reaching out. I'll get back to you shortly.", "source": "fallback"}


class SaveReplyReq(BaseModel):
    orgId: str
    conversationId: str
    text: str

@agent_tools_router.post("/save-reply")
async def save_reply(req: SaveReplyReq):
    from app.models.hostaway_conversation import HostawayConversation
    conv = await HostawayConversation.find_one(
        HostawayConversation.orgId == oid(req.orgId),
        HostawayConversation.hostawayConversationId == req.conversationId
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    from app.models.hostaway_conversation import HostawayMessage
    conv.messages.append(HostawayMessage(sender="admin", text=req.text, timestamp=datetime.utcnow().isoformat()))
    conv.needsReply = False
    await conv.save()
    return {"saved": True}


@agent_tools_router.get("/conversations")
async def list_conversations(orgId: str, listingId: str, dateFrom: str, dateTo: str):
    from app.models.hostaway_conversation import HostawayConversation
    docs = await HostawayConversation.find(
        HostawayConversation.orgId == oid(orgId),
        HostawayConversation.listingId == oid(listingId)
    ).to_list()
    seen = {}
    for conv in docs:
        if conv.hostawayConversationId not in seen:
            seen[conv.hostawayConversationId] = conv
    result = []
    for conv in seen.values():
        msgs = sorted(conv.messages or [], key=lambda m: m.timestamp or "")
        last = msgs[-1] if msgs else None
        result.append({
            "conversationId": conv.hostawayConversationId,
            "guestName": conv.guestName,
            "lastMessage": last.text if last else "No messages",
            "status": "needs_reply" if last and last.sender == "guest" else "resolved",
            "messages": [{"sender": m.sender, "text": m.text, "timestamp": m.timestamp} for m in msgs]
        })
    return {"count": len(result), "conversations": result}


@agent_tools_router.get("/guest-summary")
async def guest_summary(orgId: str, listingId: str, dateFrom: str, dateTo: str):
    from app.models.guest_summary import GuestSummary
    summary = await GuestSummary.find_one(
        GuestSummary.orgId == oid(orgId), GuestSummary.listingId == oid(listingId),
        GuestSummary.dateFrom == dateFrom, GuestSummary.dateTo == dateTo
    )
    if not summary:
        return {"cached": False, "stale": False, "summary": None}
    age_ms = (datetime.utcnow() - summary.updatedAt).total_seconds() * 1000
    stale = age_ms > 6 * 60 * 60 * 1000
    return {"cached": not stale, "stale": stale, "summary": {
        "sentiment": summary.sentiment, "themes": summary.themes,
        "actionItems": summary.actionItems, "bulletPoints": summary.bulletPoints,
        "totalConversations": summary.totalConversations, "needsReplyCount": summary.needsReplyCount
    }}


class GuestSummaryReq(BaseModel):
    orgId: str
    listingId: str
    dateFrom: str
    dateTo: str

@agent_tools_router.post("/guest-summary/generate")
async def generate_guest_summary(req: GuestSummaryReq):
    # Fetch conversations and compute summary server-side
    from app.models.hostaway_conversation import HostawayConversation
    from app.models.guest_summary import GuestSummary
    docs = await HostawayConversation.find(
        HostawayConversation.orgId == oid(req.orgId),
        HostawayConversation.listingId == oid(req.listingId)
    ).to_list()
    msgs_all = [m for d in docs for m in (d.messages or [])]
    needs_reply = sum(1 for d in docs if d.needsReply)
    total = len(docs)
    sentiment = "Needs Attention" if needs_reply > total / 2 else ("Neutral" if needs_reply > 0 else "Positive")

    summary_doc = await GuestSummary.find_one(
        GuestSummary.orgId == oid(req.orgId), GuestSummary.listingId == oid(req.listingId),
        GuestSummary.dateFrom == req.dateFrom, GuestSummary.dateTo == req.dateTo
    )
    if not summary_doc:
        summary_doc = GuestSummary(orgId=oid(req.orgId), listingId=oid(req.listingId),
                                   dateFrom=req.dateFrom, dateTo=req.dateTo)
    summary_doc.sentiment = sentiment
    summary_doc.totalConversations = total
    summary_doc.needsReplyCount = needs_reply
    summary_doc.updatedAt = datetime.utcnow()
    await summary_doc.save()
    return {"summary": {"sentiment": sentiment, "totalConversations": total, "needsReplyCount": needs_reply}, "conversationsAnalyzed": total}


# ── Nearby Comps (Haversine Proximity Search) ─────────────────────────────────

import math

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Returns distance between two lat/lon points in kilometres."""
    R = 6371.0  # Earth radius in km
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (math.sin(d_lat / 2) ** 2
         + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2))
         * math.sin(d_lon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


@agent_tools_router.get("/nearby-comps")
async def get_nearby_comps(
    lat: float,
    lon: float,
    bedrooms: int,
    month: Optional[str] = None,         # YYYY-MM-01 or YYYY-MM
    dateFrom: Optional[str] = None,
    dateTo: Optional[str] = None,
    radiusKm: float = 1.0,
    marketId: str = "2286",
    limit: int = 25,
    apiKey: Optional[str] = None,
    orgId: Optional[str] = None,
    listingId: Optional[str] = None,
):
    """
    Layer-2 query: Find competitor listings within `radiusKm` with matching
    `bedrooms`, then fetch their performance for the given `month`.

    Returns:
      - comps[]: listing detail + performance merged for each match
      - percentiles: P25/P50/P75/P90 of native_rate_avg
      - summary stats: avg_occupancy, avg_adr, count
    """
    from app.models.competitor_listing import CompetitorListing
    from app.models.competitor_performance import CompetitorPerformance

    # Normalize month to YYYY-MM-01
    effective_month = month or (dateFrom[:7] if dateFrom else datetime.now().strftime("%Y-%m"))
    date_key = effective_month.strip()
    if len(date_key) == 7:  # "2026-04" → "2026-04-01"
        date_key = f"{date_key}-01"

    # Step 1: Find all competitor listings with matching bedrooms in this market
    all_listings = await CompetitorListing.find(
        CompetitorListing.marketId == marketId,
        CompetitorListing.bedrooms == bedrooms,
    ).to_list()

    # Step 2: Filter by Haversine distance
    nearby = []
    for cl in all_listings:
        dist = _haversine_km(lat, lon, cl.latitude, cl.longitude)
        if dist <= radiusKm:
            nearby.append((cl, round(dist, 3)))

    nearby.sort(key=lambda x: x[1])
    nearby = nearby[:limit]

    if not nearby:
        return {
            "comps": [],
            "percentiles": {"p25": 0, "p50": 0, "p75": 0, "p90": 0},
            "summary": {"count": 0, "avg_occupancy": 0, "avg_adr": 0},
            "radius_km": radiusKm,
            "bedrooms": bedrooms,
            "month": date_key,
        }

    # Step 3: Fetch performance for those listing IDs for the target month
    listing_ids = [cl.airbticsListingId for cl, _ in nearby]
    perf_docs = await CompetitorPerformance.find(
        CompetitorPerformance.marketId == marketId,
        CompetitorPerformance.date == date_key,
        {"airbticsListingId": {"$in": listing_ids}},
    ).to_list()

    perf_map = {p.airbticsListingId: p for p in perf_docs}

    # Step 4: Merge listing details + performance
    comps = []
    adrs = []
    occupancies = []

    for cl, dist in nearby:
        perf = perf_map.get(cl.airbticsListingId)
        entry = {
            "listing_name": cl.listingName,
            "bedrooms": cl.bedrooms,
            "distance_km": dist,
            "rating": cl.ratingOverall,
            "num_reviews": cl.numReviews,
            "host_name": cl.hostName,
            "latitude": cl.latitude,
            "longitude": cl.longitude,
        }
        if perf:
            entry.update({
                "occupancy": perf.occupancy,
                "native_rate_avg": perf.nativeRateAvg,
                "native_revenue": perf.nativeRevenue,
                "reserved_days": perf.reservedDays,
                "vacant_days": perf.vacantDays,
                "length_of_stay_avg": perf.lengthOfStayAvg,
                "data_type": perf.dataType,
            })
            if perf.nativeRateAvg > 0:
                adrs.append(perf.nativeRateAvg)
            if perf.occupancy > 0:
                occupancies.append(perf.occupancy)
        else:
            entry.update({
                "occupancy": None,
                "native_rate_avg": None,
                "native_revenue": None,
                "reserved_days": None,
                "vacant_days": None,
                "length_of_stay_avg": None,
                "data_type": None,
            })
        comps.append(entry)

    # Step 5: Compute percentiles from the neighborhood set
    def percentile(sorted_list, pct):
        if not sorted_list:
            return 0
        k = (len(sorted_list) - 1) * pct / 100.0
        f = int(k)
        c = f + 1 if f + 1 < len(sorted_list) else f
        d = k - f
        return round(sorted_list[f] + d * (sorted_list[c] - sorted_list[f]), 1)

    adrs_sorted = sorted(adrs)
    avg_occ = round(sum(occupancies) / len(occupancies) * 100, 1) if occupancies else 0
    avg_adr = round(sum(adrs) / len(adrs), 1) if adrs else 0

    return {
        "comps": comps,
        "percentiles": {
            "p25": percentile(adrs_sorted, 25),
            "p50": percentile(adrs_sorted, 50),
            "p75": percentile(adrs_sorted, 75),
            "p90": percentile(adrs_sorted, 90),
        },
        "summary": {
            "count": len(comps),
            "with_perf_data": len(adrs),
            "avg_occupancy_pct": avg_occ,
            "avg_adr": avg_adr,
        },
        "radius_km": radiusKm,
        "bedrooms": bedrooms,
        "month": date_key,
    }


@agent_tools_router.get("/listing-perf")
async def get_listing_perf(
    marketId: str,
    listingId: str,
    month: Optional[str] = None,
):
    """
    Fetch performance data for a specific Airbtics competitor listing.
    If month is omitted, returns all months within the stored window.
    """
    from app.models.competitor_performance import CompetitorPerformance

    query = {
        "marketId": marketId,
        "airbticsListingId": listingId,
    }
    if month:
        date_key = month.strip()
        if len(date_key) == 7:
            date_key = f"{date_key}-01"
        query["date"] = date_key

    docs = await CompetitorPerformance.find(query).sort("+date").to_list()
    return {
        "listing_id": listingId,
        "months": [
            {
                "date": d.date,
                "data_type": d.dataType,
                "occupancy": d.occupancy,
                "native_rate_avg": d.nativeRateAvg,
                "native_revenue": d.nativeRevenue,
                "reserved_days": d.reservedDays,
                "vacant_days": d.vacantDays,
                "length_of_stay_avg": d.lengthOfStayAvg,
                "booking_lead_time_avg": d.bookingLeadTimeAvg,
            }
            for d in docs
        ],
    }
