from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Dict, Any, Optional

hostaway_router = APIRouter(prefix="/hostaway", tags=["hostaway"])
sync_router = APIRouter(prefix="/sync", tags=["sync"])
proposals_router = APIRouter(prefix="/proposals", tags=["proposals"])
calendar_metrics_router = APIRouter(prefix="/calendar-metrics", tags=["calendar-metrics"])
insights_router = APIRouter(prefix="/insights", tags=["insights"])
organizations_router = APIRouter(prefix="/organizations", tags=["organizations"])
properties_router = APIRouter(prefix="/properties", tags=["properties"])
reservations_router = APIRouter(prefix="/reservations", tags=["reservations"])
benchmark_router = APIRouter(prefix="/benchmark", tags=["benchmark"])
chat_router = APIRouter(prefix="/chat", tags=["chat"])
events_router = APIRouter(prefix="/events", tags=["events"])

# --- Hostaway ---
@hostaway_router.post("/webhook")
async def hostaway_webhook(payload: Dict[str, Any]):
    return {"success": True, "message": "Webhook placeholder parsed"}

# --- Sync ---
@sync_router.post("/")
async def trigger_sync(source: str):
    return {"success": True, "message": f"Sync triggered for {source}"}

@sync_router.get("/status")
async def get_sync_status(orgId: str, propertyId: str = None):
    from app.models.listing import Listing
    from app.models.reservation import Reservation
    from app.models.inventory_master import InventoryMaster
    from bson import ObjectId

    try:
        org_oid = ObjectId(orgId)
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid orgId: {orgId}")

    listing_filter = [Listing.orgId == org_oid]
    reservation_filter = [Reservation.orgId == org_oid]
    inventory_filter = [InventoryMaster.orgId == org_oid]

    if propertyId:
        try:
            listing_oid = ObjectId(propertyId)
        except Exception:
            raise HTTPException(status_code=400, detail=f"Invalid propertyId: {propertyId}")
        listing_filter.append(Listing.id == listing_oid)
        reservation_filter.append(Reservation.listingId == listing_oid)
        inventory_filter.append(InventoryMaster.listingId == listing_oid)

    listings_count = await Listing.find(*listing_filter).count()
    reservations_count = await Reservation.find(*reservation_filter).count()
    inventory_days_count = await InventoryMaster.find(*inventory_filter).count()

    latest_listing = await Listing.find(*listing_filter).sort(-Listing.updatedAt).first_or_none()
    latest_reservation = await Reservation.find(*reservation_filter).sort(-Reservation.updatedAt).first_or_none()
    latest_inventory = await InventoryMaster.find(*inventory_filter).sort(-InventoryMaster.updatedAt).first_or_none()

    return {
        "listings": {
            "count": listings_count,
            "lastSyncedAt": latest_listing.updatedAt.isoformat() if latest_listing else None,
        },
        "reservations": {
            "count": reservations_count,
            "lastSyncedAt": latest_reservation.updatedAt.isoformat() if latest_reservation else None,
        },
        "inventory_master": {
            "daysCount": inventory_days_count,
            "lastSyncedAt": latest_inventory.updatedAt.isoformat() if latest_inventory else None,
        },
    }

@sync_router.post("/trigger")
async def trigger_sync_now(source: str = "manual"):
    return {"success": True, "message": f"Sync triggered for {source}"}

# --- Proposals ---
@proposals_router.get("")
async def get_proposals(listingId: str = None):
    return {"proposals": []}

@proposals_router.post("/{proposal_id}/approve")
async def approve_proposal(proposal_id: str):
    return {"success": True}

# --- Calendar Metrics ---
@calendar_metrics_router.get("")
async def get_calendar_metrics(listingId: str, from_date: str = Query(None, alias="from"), to: str = Query(None)):
    from app.models.inventory_master import InventoryMaster
    from app.models.reservation import Reservation
    from bson import ObjectId
    from datetime import datetime, timedelta

    if not from_date:
        from_date = datetime.utcnow().date().isoformat()
    if not to:
        to = (datetime.utcnow().date() + timedelta(days=29)).isoformat()

    print(f">>> [GET /calendar-metrics] listingId={listingId}, from={from_date}, to={to}")

    inv_docs = await InventoryMaster.find(
        InventoryMaster.listingId == ObjectId(listingId),
        InventoryMaster.date >= from_date,
        InventoryMaster.date <= to
    ).to_list()

    total_days = len(inv_docs)
    booked_days = len([x for x in inv_docs if x.status == "booked"])
    blocked_days = len([x for x in inv_docs if x.status == "blocked"])
    available_days = total_days - booked_days - blocked_days
    
    occupancy = round((booked_days / max(1, total_days)) * 100)
    avg_price = round(sum(float(x.currentPrice or 0) for x in inv_docs) / max(1, total_days))
    
    print(f"    [CALENDAR DATA] total={total_days}, booked={booked_days}, occ={occupancy}%")

    return {
        "occupancy": occupancy,
        "avgPrice": avg_price,
        "bookedDays": booked_days,
        "availableDays": available_days,
        "blockedDays": blocked_days,
        "totalDays": total_days,
        "calendarDays": [
            {
                "date": x.date,
                "price": float(x.currentPrice or 0),
                "status": x.status,
                "proposalStatus": x.proposalStatus
            }
            for x in inv_docs
        ],
        "reservations": [] # Simplified for now
    }

# --- Insights ---
@insights_router.get("")
async def get_insights(listingId: str = None, orgId: str = None):
    from app.models.inventory_master import InventoryMaster
    from bson import ObjectId
    
    print(f">>> [GET /insights] listingId={listingId}, orgId={orgId}")

    # Dynamic insights generator
    insights = []
    
    if listingId and listingId != "None":
        try:
            inv = await InventoryMaster.find(InventoryMaster.listingId == ObjectId(listingId)).to_list(100)
            booked = [x for x in inv if x.status == "booked"]
            if len(booked) < 5:
                insights.append({
                    "id": "low_occ",
                    "title": "Low Occupancy Alert",
                    "description": "Your occupancy is below 20% for the next 30 days. Consider a 'Surge' strategy.",
                    "severity": "high",
                    "category": "performance"
                })
            
            pending = [x for x in inv if x.proposalStatus == "pending"]
            if pending:
                insights.append({
                    "id": "pending_proposals",
                    "title": f"{len(pending)} Pending Proposals",
                    "description": "Aria has generated new pricing proposals that require your review.",
                    "severity": "medium",
                    "category": "proposals"
                })
        except Exception as e:
            print(f"⚠️ [ERROR] Failed to fetch insights for listing {listingId}: {e}")

    if not insights:
        insights.append({
            "id": "market_trend",
            "title": "Market Pacing Up",
            "description": "Demand in your area is up by 12% for the coming weekend.",
            "severity": "info",
            "category": "market"
        })

    return {"insights": insights}

# --- Events ---
@events_router.get("")
async def get_events(listingId: str = None, orgId: str = None):
    from app.models.market_event import MarketEvent
    from app.services.market_intelligence import sync_external_market_intelligence
    from datetime import datetime, timedelta
    from bson import ObjectId
    from beanie import PydanticObjectId
    
    print(f">>> [GET /events] listingId={listingId}, orgId={orgId}")
    
    today = datetime.utcnow().strftime("%Y-%m-%d")
    future = (datetime.utcnow() + timedelta(days=90)).strftime("%Y-%m-%d")

    if not orgId:
        return {"events": []}

    # 1. Try to find real events in DB first
    events = await MarketEvent.find(
        MarketEvent.orgId == PydanticObjectId(orgId),
        MarketEvent.isActive == True,
        MarketEvent.endDate >= today
    ).sort(+MarketEvent.startDate).to_list(100)
    
    # 2. Trigger agentic sync if empty
    if not events and orgId and orgId != "None":
        print(f"    [DASHBOARD] No signals found in DB. Triggering agentic sync for org {orgId}...")
        try:
            # We wait for the sync to complete to show fresh data on first load
            await sync_external_market_intelligence(
                org_id=ObjectId(orgId),
                city="Dubai",
                area="Dubai Marina",
                date_from=today,
                date_to=future
            )
        except Exception as e:
            print(f"⚠️ [ERROR] Failed to sync market intelligence for org {orgId}: {e}")
        
        # Re-fetch
        events = await MarketEvent.find(
            MarketEvent.orgId == PydanticObjectId(orgId),
            MarketEvent.isActive == True,
            MarketEvent.endDate >= today
        ).sort(+MarketEvent.startDate).to_list(100)

    if not events:
        # Provide some fallback events for UI polish
        return {"events": [
            {
                "_id": "mock_1",
                "name": "Dubai Food Festival 2026",
                "startDate": "2026-04-25",
                "endDate": "2026-05-10",
                "impactLevel": "high",
                "upliftPct": 15.0,
                "description": "City-wide culinary celebration driving high demand for short-term rentals.",
                "source": "market_template",
                "area": "Dubai",
                "isActive": True
            },
            {
                "_id": "mock_2",
                "name": "Eid Al Fitr Holidays",
                "startDate": "2026-03-30",
                "endDate": "2026-04-02",
                "impactLevel": "high",
                "upliftPct": 25.0,
                "description": "Major public holiday with high regional travel and staycation demand.",
                "source": "market_template",
                "area": "Dubai",
                "isActive": True
            }
        ]}

    return {"events": [
        {"_id": str(e.id), "name": e.name, "startDate": e.startDate, "endDate": e.endDate,
         "impactLevel": e.impactLevel, "upliftPct": float(e.upliftPct or 0),
         "description": e.description, "source": e.source, "area": getattr(e, "area", None)}
        for e in events
    ]}

# --- Organizations ---
@organizations_router.get("/{org_id}")
async def get_organization(org_id: str):
    return {"id": org_id, "name": "Default Org"}

# --- Properties/Groups ---
@properties_router.get("")
async def get_properties(orgId: str):
    from app.models.listing import Listing
    from app.models.inventory_master import InventoryMaster
    from app.models.reservation import Reservation
    from bson import ObjectId
    from datetime import datetime, timedelta

    org_oid = ObjectId(orgId)
    listings = await Listing.find(Listing.orgId == org_oid).to_list()
    listing_ids = [l.id for l in listings]

    now = datetime.utcnow().date()
    from_date = now.isoformat()
    to_date = (now + timedelta(days=29)).isoformat()

    # Fetch only needed fields to save memory and time
    inv_docs = await InventoryMaster.find(
        InventoryMaster.orgId == org_oid,
        InventoryMaster.date >= from_date,
        InventoryMaster.date <= to_date
    ).to_list()
    
    # FOR RESERVATIONS: Use a projection model to avoid AttributeError
    class ReservationProjection(BaseModel):
        listingId: Optional[Any]
        totalPrice: Optional[float]
        channelName: Optional[str]

    res_docs = await Reservation.find(Reservation.orgId == org_oid).project(ReservationProjection).to_list()

    inv_by_listing: dict[str, list] = {}
    for d in inv_docs:
        inv_by_listing.setdefault(str(d.listingId), []).append(d)

    res_by_listing: dict[str, list] = {}
    for r in res_docs:
        # project returns instances of ReservationProjection
        lid = str(r.listingId or "")
        res_by_listing.setdefault(lid, []).append(r)

    properties = []
    for l in listings:
        lid = str(l.id)
        listing_inv = inv_by_listing.get(lid, [])
        listing_res = res_by_listing.get(lid, [])
        booked_days = len([x for x in listing_inv if x.status == "booked"])
        occupancy = round((booked_days / len(listing_inv)) * 100) if listing_inv else 0
        avg_price = round(sum(float(x.currentPrice or 0) for x in listing_inv) / len(listing_inv)) if listing_inv else round(float(l.price or 0))
        pending = len([x for x in listing_inv if x.proposalStatus == "pending"])
        revenue = round(sum(float(x.currentPrice or 0) for x in listing_inv if x.status == "booked"), 2)

        channel_map: dict[str, dict] = {}
        for r in listing_res:
            channel = r.channelName or "Direct"
            if channel not in channel_map:
                channel_map[channel] = {"channel": channel, "revenue": 0.0, "count": 0}
            channel_map[channel]["revenue"] += float(r.totalPrice or 0)
            channel_map[channel]["count"] += 1

        properties.append({
            "id": lid,
            "name": l.name,
            "city": l.city,
            "area": l.area,
            "bedrooms": l.bedroomsNumber,
            "bathrooms": l.bathroomsNumber,
            "basePrice": float(l.price or 0),
            "price": float(l.price or 0),
            "currency": l.currencyCode or "AED",
            "currencyCode": l.currencyCode or "AED",
            "priceFloor": float(l.priceFloor or 0),
            "priceCeiling": float(l.priceCeiling or 0),
            "capacity": l.personCapacity,
            "hostawayId": l.hostawayId,
            "propertyType": str(l.propertyTypeId or "N/A"),
            "isActive": bool(l.isActive),
            "isActivated": bool(l.isActive),
            "occupancyPct": occupancy,
            "avgPrice": avg_price,
            "pendingProposals": pending,
            "totalReservations": len(listing_res),
            "totalRevenue": revenue,
            "revenueByChannel": list(channel_map.values()),
            "createdAt": l.createdAt.isoformat() if l.createdAt else None,
        })

    return {"properties": properties}

@properties_router.post("/activate")
async def activate_property(body: Dict[str, Any]):
    from app.models.listing import Listing
    from bson import ObjectId

    listing_id = body.get("listingId")
    if not listing_id:
        return {"success": False, "error": "listingId is required"}
    listing = await Listing.get(ObjectId(listing_id))
    if not listing:
        return {"success": False, "error": "Listing not found"}
    listing.isActive = True
    await listing.save()
    return {"success": True}

@properties_router.post("/deactivate")
async def deactivate_property(body: Dict[str, Any]):
    from app.models.listing import Listing
    from bson import ObjectId

    listing_id = body.get("listingId")
    if not listing_id:
        return {"success": False, "error": "listingId is required"}
    listing = await Listing.get(ObjectId(listing_id))
    if not listing:
        return {"success": False, "error": "Listing not found"}
    listing.isActive = False
    await listing.save()
    return {"success": True}

@properties_router.get("/analytics")
async def get_property_analytics(
    listingId: str,
    from_date: str = Query(None, alias="from"),
    to: str = Query(None),
):
    from app.models.listing import Listing
    from app.models.reservation import Reservation
    from app.models.inventory_master import InventoryMaster
    from bson import ObjectId
    from datetime import datetime, timedelta

    listing = await Listing.get(ObjectId(listingId))
    if not listing:
        return {"error": "Listing not found"}

    date_from = from_date
    date_to = to
    if not date_from:
        date_from = datetime.utcnow().date().isoformat()
    if not date_to:
        date_to = (datetime.utcnow().date() + timedelta(days=29)).isoformat()

    inv_docs = await InventoryMaster.find(
        InventoryMaster.listingId == listing.id,
        InventoryMaster.date >= date_from,
        InventoryMaster.date <= date_to
    ).sort(+InventoryMaster.date).to_list()
    res_docs = await Reservation.find(
        Reservation.listingId == listing.id,
        Reservation.checkIn <= date_to,
        Reservation.checkOut >= date_from
    ).to_list()

    total_bookings = len(res_docs)
    total_revenue = round(sum(float(r.totalPrice or 0) for r in res_docs), 2)
    total_nights = sum(int(r.nights or 0) for r in res_docs)
    avg_los = round(total_nights / total_bookings, 2) if total_bookings else 0
    booked_days = len([x for x in inv_docs if x.status == "booked"])
    occupancy = round((booked_days / len(inv_docs)) * 100, 2) if inv_docs else 0

    channel_map: dict[str, dict] = {}
    for r in res_docs:
        ch = r.channelName or "Direct"
        if ch not in channel_map:
            channel_map[ch] = {"channel": ch, "revenue": 0.0, "bookings": 0}
        channel_map[ch]["revenue"] += float(r.totalPrice or 0)
        channel_map[ch]["bookings"] += 1

    channel_mix = []
    for v in channel_map.values():
        channel_mix.append({
            **v,
            "revenuePct": round((v["revenue"] / total_revenue) * 100, 2) if total_revenue else 0,
        })

    by_date_inv: dict[str, list] = {}
    for d in inv_docs:
        by_date_inv.setdefault(d.date, []).append(d)

    occupancy_trend = []
    adr_revpar_trend = []
    booking_velocity_map: dict[str, int] = {}
    for r in res_docs:
        key = (r.createdAt.date().isoformat() if r.createdAt else r.checkIn)
        booking_velocity_map[key] = booking_velocity_map.get(key, 0) + 1

    for day, items in sorted(by_date_inv.items()):
        booked = len([i for i in items if i.status == "booked"])
        blocked = len([i for i in items if i.status == "blocked"])
        total = len(items)
        occupancy_trend.append({
            "date": day,
            "totalDays": total,
            "bookedDays": booked,
            "blockedDays": blocked,
            "occupancyPct": round((booked / total) * 100, 2) if total else 0,
        })
        booked_prices = [float(i.currentPrice or 0) for i in items if i.status == "booked"]
        adr = round(sum(booked_prices) / len(booked_prices), 2) if booked_prices else 0
        revpar = round((sum(booked_prices) / total), 2) if total else 0
        adr_revpar_trend.append({
            "date": day,
            "adr": adr,
            "revpar": revpar,
            "bookedRevenue": round(sum(booked_prices), 2),
        })

    booking_velocity = []
    for day, count in sorted(booking_velocity_map.items()):
        booking_velocity.append({"date": day, "bookings": count, "movingAvg7d": count})

    los_distribution_map: dict[str, int] = {}
    for r in res_docs:
        n = int(r.nights or 0)
        if n <= 2:
            bucket = "1-2"
        elif n <= 5:
            bucket = "3-5"
        elif n <= 10:
            bucket = "6-10"
        else:
            bucket = "10+"
        los_distribution_map[bucket] = los_distribution_map.get(bucket, 0) + 1

    los_distribution = [{"bucket": k, "bookings": v} for k, v in los_distribution_map.items()]

    return {
        "listingId": str(listing.id),
        "propertyName": listing.name,
        "dateRange": {"from": date_from, "to": date_to},
        "summary": {
            "totalBookings": total_bookings,
            "totalRevenue": total_revenue,
            "avgLos": avg_los,
            "occupancyPct": occupancy,
            "avgDailyRevenue": round(total_revenue / max(1, len(by_date_inv)), 2),
        },
        "bookingVelocity": booking_velocity,
        "losDistribution": los_distribution,
        "occupancyTrend": occupancy_trend,
        "adrRevparTrend": adr_revpar_trend,
        "channelMix": channel_mix,
    }

# --- Reservations ---
@reservations_router.get("")
async def get_reservations(orgId: str = None, listingId: str = None, checkIn: str = None, checkOut: str = None):
    from app.models.reservation import Reservation
    from bson import ObjectId

    filters = []
    if orgId:
        filters.append(Reservation.orgId == ObjectId(orgId))
    if listingId:
        filters.append(Reservation.listingId == ObjectId(listingId))
    if checkIn:
        filters.append(Reservation.checkOut >= checkIn)
    if checkOut:
        filters.append(Reservation.checkIn <= checkOut)

    docs = await Reservation.find(*filters).to_list()
    return {
        "reservations": [
            {"id": str(r.id), "listingId": str(r.listingId), **r.model_dump(exclude={"id", "listingId", "orgId"})}
            for r in docs
        ]
    }

# --- Benchmark ---
@benchmark_router.get("")
async def get_benchmarks(listingId: str = None):
    return {"recommendedWeekday": 0, "recommendedWeekend": 0, "p50Rate": 0, "comps": []}

# --- Chat ---
class ChatRequest(BaseModel):
    message: str
@chat_router.post("/")
async def chat_interaction(req: ChatRequest):
    return {"response": "Placeholder chat agent response", "parsedJson": None}
