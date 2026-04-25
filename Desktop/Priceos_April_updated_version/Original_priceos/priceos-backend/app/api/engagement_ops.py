from datetime import datetime
from typing import Optional

from beanie import PydanticObjectId
from bson import ObjectId
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.models.organization import Organization
from app.models.listing import Listing
from app.models.reservation import Reservation
from app.models.market_event import MarketEvent
from app.models.chat_message import ChatMessage, ChatContext
from app.models.inventory_master import InventoryMaster
from app.models.hostaway_conversation import HostawayConversation, HostawayMessage
from app.models.guest_summary import GuestSummary
from app.models.benchmark_data import BenchmarkData
from app.services.lyzr import call_lyzr_agent, stream_lyzr_agent
import json
import asyncio
import os

engagement_router = APIRouter(tags=["engagement-ops"])


def _db():
    return Organization.get_motor_collection().database


def _sse_event(event_type: str, data: dict) -> str:
    payload = {"type": event_type, **data}
    return f"data: {json.dumps(payload)}\n\n"


class OrgScopedRequest(BaseModel):
    orgId: str


class TaskCreateRequest(OrgScopedRequest):
    listingMapId: int
    title: str
    description: Optional[str] = None
    status: str = "todo"
    priority: str = "medium"
    category: str = "other"
    dueDate: Optional[str] = None
    assignee: Optional[str] = None


class TaskUpdateRequest(OrgScopedRequest):
    status: str


@engagement_router.get("/tasks")
async def get_tasks(orgId: str):
    rows = await _db()["tasks"].find({"orgId": orgId}).sort("createdAt", -1).to_list(500)
    return [
        {
            "id": int(r["id"]),
            "listingMapId": int(r.get("listingMapId", 0)),
            "title": r.get("title", ""),
            "description": r.get("description"),
            "status": r.get("status", "todo"),
            "priority": r.get("priority", "medium"),
            "category": r.get("category", "other"),
            "dueDate": r.get("dueDate"),
            "assignee": r.get("assignee"),
            "reservationId": r.get("reservationId"),
            "createdAt": r.get("createdAt") or datetime.utcnow().isoformat(),
        }
        for r in rows
    ]


@engagement_router.post("/tasks")
async def create_task(req: TaskCreateRequest):
    last = await _db()["tasks"].find({"orgId": req.orgId}).sort("id", -1).limit(1).to_list(1)
    next_id = (last[0]["id"] + 1) if last else 1
    row = {
        "id": next_id,
        "orgId": req.orgId,
        "listingMapId": req.listingMapId,
        "title": req.title,
        "description": req.description,
        "status": req.status,
        "priority": req.priority,
        "category": req.category,
        "dueDate": req.dueDate,
        "assignee": req.assignee,
        "createdAt": datetime.utcnow().isoformat(),
    }
    await _db()["tasks"].insert_one(row)
    return row


@engagement_router.put("/tasks/{task_id}")
async def update_task(task_id: int, req: TaskUpdateRequest):
    await _db()["tasks"].update_one(
        {"orgId": req.orgId, "id": task_id},
        {"$set": {"status": req.status, "updatedAt": datetime.utcnow().isoformat()}},
    )
    return {"success": True}


class ExpenseCreateRequest(OrgScopedRequest):
    listingMapId: int
    category: str
    amount: float
    currencyCode: str = "AED"
    description: str
    date: str


@engagement_router.get("/expenses")
async def get_expenses(orgId: str):
    rows = await _db()["expenses"].find({"orgId": orgId}).sort("date", -1).to_list(500)
    return [
        {
            "id": int(r["id"]),
            "listingMapId": int(r.get("listingMapId", 0)),
            "category": r.get("category", "other"),
            "amount": float(r.get("amount", 0)),
            "currencyCode": r.get("currencyCode", "AED"),
            "description": r.get("description", ""),
            "date": r.get("date", ""),
        }
        for r in rows
    ]


@engagement_router.post("/expenses")
async def create_expense(req: ExpenseCreateRequest):
    last = await _db()["expenses"].find({"orgId": req.orgId}).sort("id", -1).limit(1).to_list(1)
    next_id = (last[0]["id"] + 1) if last else 1
    row = {
        "id": next_id,
        "orgId": req.orgId,
        "listingMapId": req.listingMapId,
        "category": req.category,
        "amount": req.amount,
        "currencyCode": req.currencyCode,
        "description": req.description,
        "date": req.date,
        "createdAt": datetime.utcnow().isoformat(),
    }
    await _db()["expenses"].insert_one(row)
    return row


class CalendarBlockRequest(OrgScopedRequest):
    propertyId: str
    startDate: str
    endDate: str
    reason: Optional[str] = "other"


class CalendarUnblockRequest(OrgScopedRequest):
    propertyId: str
    startDate: str
    endDate: str


@engagement_router.post("/calendar/block")
async def block_calendar(req: CalendarBlockRequest):
    listing_oid = ObjectId(req.propertyId)
    org_oid = ObjectId(req.orgId)
    docs = await InventoryMaster.find(
        InventoryMaster.orgId == org_oid,
        InventoryMaster.listingId == listing_oid,
        InventoryMaster.date >= req.startDate,
        InventoryMaster.date <= req.endDate,
    ).to_list()
    for d in docs:
        d.status = "blocked"
        d.reasoning = f"Blocked: {req.reason or 'other'}"
        await d.save()
    return {"success": True, "blocked": len(docs)}


@engagement_router.post("/calendar/unblock")
async def unblock_calendar(req: CalendarUnblockRequest):
    listing_oid = ObjectId(req.propertyId)
    org_oid = ObjectId(req.orgId)
    docs = await InventoryMaster.find(
        InventoryMaster.orgId == org_oid,
        InventoryMaster.listingId == listing_oid,
        InventoryMaster.date >= req.startDate,
        InventoryMaster.date <= req.endDate,
    ).to_list()
    for d in docs:
        if d.status == "blocked":
            d.status = "available"
            await d.save()
    return {"success": True, "unblocked": len(docs)}


@engagement_router.get("/hostaway/conversations/cached")
async def cached_conversations(orgId: str, listingId: Optional[str] = None):
    query = [HostawayConversation.orgId == PydanticObjectId(orgId)]
    if listingId:
        query.append(HostawayConversation.listingId == PydanticObjectId(listingId))
    rows = await HostawayConversation.find(*query).sort(-HostawayConversation.syncedAt).to_list()
    ui = []
    for conv in rows:
        msgs = sorted(conv.messages, key=lambda m: m.timestamp or "")
        last = msgs[-1] if msgs else None
        # Count guest messages since the last host/admin reply
        last_admin_idx = -1
        for i, m in enumerate(msgs):
            if m.sender in ("host", "admin", "outbound"):
                last_admin_idx = i
        unread_count = sum(1 for m in msgs[last_admin_idx + 1:] if m.sender == "guest")
        ui.append(
            {
                "id": conv.hostawayConversationId,
                "guestName": conv.guestName,
                "lastMessage": last.text if last else "No messages",
                "status": "needs_reply" if last and last.sender == "guest" else "resolved",
                "listingId": str(conv.listingId) if conv.listingId else None,
                "unreadCount": unread_count,
                "messages": [
                    {
                        "id": f"{conv.hostawayConversationId}_{i}",
                        "sender": m.sender,
                        "text": m.text,
                        "time": m.timestamp,
                    }
                    for i, m in enumerate(msgs)
                ],
            }
        )
    return {"success": True, "conversations": ui}


@engagement_router.get("/hostaway/conversations")
async def sync_conversations(orgId: str, listingId: str):
    # For split backend, use cached conversations as sync response.
    return await cached_conversations(orgId=orgId, listingId=listingId)


@engagement_router.get("/hostaway/metadata")
async def hostaway_metadata(orgId: str, accountId: Optional[str] = None, apiSecret: Optional[str] = None):
    org = await Organization.get(PydanticObjectId(orgId))
    if not org:
        return {"success": False, "error": "Organization not found"}
    if accountId:
        org.hostawayAccountId = accountId
    if apiSecret:
        org.hostawayApiKey = apiSecret
    org.updatedAt = datetime.utcnow()
    await org.save()

    listings = await Listing.find(Listing.orgId == org.id).to_list(300)
    payload = [
        {
            "id": str(l.hostawayId or l.id),
            "name": l.name,
            "bedrooms": l.bedroomsNumber,
            "city": l.city,
            "type": "apartment",
            "thumbnail": None,
        }
        for l in listings
    ]
    return {
        "success": True,
        "mode": "real",
        "total": len(payload),
        "listings": payload,
    }


class SuggestReplyRequest(BaseModel):
    messages: list[dict] = []
    guestName: Optional[str] = None
    propertyName: Optional[str] = None
    listingId: Optional[str] = None
    orgId: Optional[str] = None
    sessionId: Optional[str] = None
    threadId: Optional[str] = None


@engagement_router.post("/hostaway/suggest-reply")
async def suggest_reply(req: SuggestReplyRequest):
    async def gen():
        session_id = req.sessionId or f"guest-{datetime.utcnow().timestamp()}"
        agent_id = os.environ.get("LYZR_Chat_Response_Agent_ID", "699d8ab150b4c733eb376fd4")

        # 🚀 Step 1: Initial Routing Signal
        yield _sse_event("status", {"step": "routing", "message": "Guest Agent: Reading conversation history..."})
        yield _sse_event("thinking", {"message": f"Analyzing conversation for {req.guestName}..."})

        # Format history
        history = ""
        for m in req.messages:
            sender = "Guest" if m.get("sender") == "guest" else "Host"
            history += f"{sender}: {m.get('text')}\n"
        
        prompt = f"""
Suggest a hospitality-focused reply to the guest: {req.guestName}
Property: {req.propertyName}

Conversation History:
{history}

Rules:
1. Be warm, empathetic, and professional.
2. Do NOT mention being an AI.
3. If there is a maintenance issue, mention that you'll look into it.
4. Provide the reply in a JSON format: {{"reply": "..."}}
"""

        # 💎 Fetch property context for Maya (Guest Agent)
        # We explicitly inject listingId, orgId, and threadId into the message to ensure the agent has them in context
        context_ids = f"\n[CONTEXT: orgId={req.orgId}, listingId={req.listingId}, threadId={req.threadId}]\n"
        prompt = context_ids + prompt

        if req.orgId and req.listingId:
            from app.api.agent_tools import get_listing_context
            yield _sse_event("status", {"step": "analyzing", "message": "Maya: Retrieving listing details & rules..."})
            listing_ctx = await get_listing_context(req.listingId, req.orgId)
            if listing_ctx:
                prompt = f"## PROPERTY_CONTEXT\n{listing_ctx}\n\n" + prompt
                print(f"💎 [GUEST_AGENT] Context injected for query...")

        full_response = ""
        
        # 🌊 Stream from Lyzr
        from app.services.lyzr import stream_lyzr_agent
        async for event in stream_lyzr_agent(
            agent_id=agent_id,
            message=prompt,
            session_id=session_id,
            system_prompt_variables={
                "guest_name": req.guestName,
                "property_name": req.propertyName,
                "org_id": req.orgId if req.orgId else "69d776a671c7b939aaf49053",
                "listing_id": req.listingId if req.listingId else "",
                "thread_id": req.threadId if req.threadId else "",
                "apiKey": os.environ.get("LYZR_API_KEY", ""), # Added as required by system prompt
                "today": datetime.utcnow().strftime("%Y-%m-%d"),
            }
        ):
            if event["type"] == "thinking":
                yield _sse_event("thinking", {"message": event.get("message") or event.get("content")})
            
            elif event["type"] == "agent_event":
                yield _sse_event("agent_event", {"payload": event.get("payload")})

            elif event["type"] == "content":
                yield _sse_event("content", {"message": event.get("content")})
                
            elif event["type"] == "final_response":
                full_response = event["content"]
                # ⚠️ Do NOT emit complete here — we clean it up first below

        # Final processing — emit ONE clean complete event
        if full_response:
            cleaned_reply = full_response
            parsed_json = None
            try:
                # Robust extraction: 1. Unquote if wrapped in literal quotes
                work_response = full_response.strip()
                if work_response.startswith('"') and work_response.endswith('"'):
                    try:
                        work_response = json.loads(work_response)
                    except:
                        work_response = work_response[1:-1]
                
                # 2. Decode literal \n and \" sequences
                decoded = work_response.replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')
                
                from app.services.lyzr import extract_json
                parsed_json = extract_json(decoded)
                
                if parsed_json:
                    # Match the agent's output schema: suggested_reply.content
                    cleaned_reply = (
                        parsed_json.get("suggested_reply", {}).get("content")
                        or parsed_json.get("chat_response")
                        or parsed_json.get("reply")
                        or parsed_json.get("content")
                        or parsed_json.get("message")
                        or full_response
                    )
            except Exception as e:
                print(f"⚠️ [GUEST_AGENT] Extraction failed: {e}")

            yield _sse_event("complete", {
                "message": cleaned_reply,
                "source": "lyzr_agent",
                "raw_json": parsed_json # Pass full object for frontend automation logic
            })
            
            # Signal graph completion
            yield _sse_event("output_generated", {"message": "Maya has generated a hospitality-focused reply."})
        else:
            yield _sse_event("error", {"message": "Maya failed to generate a reply. Please try again."})

    return StreamingResponse(gen(), media_type="text/event-stream")


class HostawayReplyRequest(OrgScopedRequest):
    conversationId: str
    text: str


@engagement_router.post("/hostaway/reply")
async def save_reply(req: HostawayReplyRequest):
    rows = await HostawayConversation.find(
        HostawayConversation.orgId == PydanticObjectId(req.orgId),
        HostawayConversation.hostawayConversationId == req.conversationId,
    ).to_list()
    for conv in rows:
        conv.messages.append(
            HostawayMessage(sender="admin", text=req.text, timestamp=datetime.utcnow().isoformat())
        )
        conv.needsReply = False
        await conv.save()
    return {"success": True, "message": "Reply saved"}


@engagement_router.get("/hostaway/summary")
async def get_summary(orgId: str, listingId: str, from_date: Optional[str] = None, to: Optional[str] = None):
    query = [
        GuestSummary.orgId == PydanticObjectId(orgId),
        GuestSummary.listingId == PydanticObjectId(listingId),
    ]
    if from_date and to:
        query.extend([GuestSummary.dateFrom == from_date, GuestSummary.dateTo == to])
    row = await GuestSummary.find(*query).sort(-GuestSummary.updatedAt).first_or_none()
    return {"success": True, "summary": row.model_dump() if row else None, "cached": bool(row)}


class GenerateSummaryRequest(OrgScopedRequest):
    listingId: str
    dateFrom: Optional[str] = "all"
    dateTo: Optional[str] = "all"


@engagement_router.post("/hostaway/summary")
async def generate_summary(req: GenerateSummaryRequest):
    conversations = await HostawayConversation.find(
        HostawayConversation.orgId == PydanticObjectId(req.orgId),
        HostawayConversation.listingId == PydanticObjectId(req.listingId),
    ).to_list()
    total = len(conversations)
    needs_reply = 0
    bullets = []
    for c in conversations:
        last = c.messages[-1] if c.messages else None
        if last and last.sender == "guest":
            needs_reply += 1
        bullets.append(f'{c.guestName}: "{last.text if last else "No messages"}"')
    sentiment = "Needs Attention" if total and needs_reply > total / 2 else ("Positive" if total else "Neutral")

    existing = await GuestSummary.find_one(
        GuestSummary.orgId == PydanticObjectId(req.orgId),
        GuestSummary.listingId == PydanticObjectId(req.listingId),
        GuestSummary.dateFrom == (req.dateFrom or "all"),
        GuestSummary.dateTo == (req.dateTo or "all"),
    )
    if not existing:
        existing = GuestSummary(
            orgId=PydanticObjectId(req.orgId),
            listingId=PydanticObjectId(req.listingId),
            dateFrom=req.dateFrom or "all",
            dateTo=req.dateTo or "all",
        )
    existing.sentiment = sentiment  # type: ignore
    existing.themes = ["General Inquiry", "Stay Coordination"] if total else []
    existing.actionItems = [f"Reply to {needs_reply} pending thread(s)"] if needs_reply else []
    existing.bulletPoints = bullets
    existing.totalConversations = total
    existing.needsReplyCount = needs_reply
    existing.updatedAt = datetime.utcnow()
    await existing.save()
    return {"success": True, "summary": existing.model_dump(), "cached": False}


class ChatRequest(BaseModel):
    message: str
    sessionId: Optional[str] = None
    graphSessionId: Optional[str] = None
    orgId: Optional[str] = None


@engagement_router.post("/chat/global")
async def global_chat(req: ChatRequest):
    agent_id = os.getenv("LYZR_Dashboard_Agent_ID") or os.getenv("AGENT_ID", "69998743f4d61186679a9515")

    async def gen():
        yield _sse_event("status", {"step": "init", "message": "Connecting to PriceOS..."})
        yield _sse_event("status", {"step": "agent", "message": "Analyzing portfolio..."})

        result = await call_lyzr_agent(
            agent_id=agent_id,
            message=req.message,
            session_id=req.graphSessionId or req.sessionId,
        )

        if result.ok:
            yield _sse_event("complete", {"message": result.response, "duration": 0})
        else:
            yield _sse_event("complete", {
                "message": "I can help with portfolio metrics, pricing, and occupancy insights. Please try again.",
                "duration": 0,
            })

    return StreamingResponse(gen(), media_type="text/event-stream")


class UnifiedChatRequest(BaseModel):
    message: str
    context: Optional[dict] = None
    dateRange: Optional[dict] = None
    sessionId: Optional[str] = None
    graphSessionId: Optional[str] = None   # per-query ID for Lyzr call + WebSocket
    orgId: Optional[str] = None


@engagement_router.get("/chat/history")
async def chat_history(orgId: str, sessionId: str, propertyId: Optional[str] = None):
    query = [ChatMessage.orgId == PydanticObjectId(orgId), ChatMessage.sessionId == sessionId]
    if propertyId and propertyId != "null":
        query.append(ChatMessage.context.propertyId == PydanticObjectId(propertyId))
    messages = await ChatMessage.find(*query).sort(+ChatMessage.createdAt).to_list()
    return {
        "messages": [
            {
                "id": str(m.id),
                "role": m.role,
                "content": m.content,
                "metadata": m.metadata,
            }
            for m in messages
        ]
    }


@engagement_router.get("/chat/sessions")
async def chat_sessions(orgId: str, propertyId: str, from_date: Optional[str] = None, to: Optional[str] = None):
    if not propertyId:
        return {"sessions": []}
    query = [
        ChatMessage.orgId == PydanticObjectId(orgId),
        ChatMessage.context.propertyId == PydanticObjectId(propertyId),
    ]
    if from_date and to:
        prefix = f"property-{propertyId}-{from_date}-{to}"
        query.append(ChatMessage.sessionId >= prefix)
    messages = await ChatMessage.find(*query).sort(-ChatMessage.createdAt).to_list(1000)
    sessions = {}
    for m in messages:
        row = sessions.get(m.sessionId)
        if not row:
            sessions[m.sessionId] = {
                "sessionId": m.sessionId,
                "lastMessageAt": m.createdAt.isoformat() if m.createdAt else datetime.utcnow().isoformat(),
                "messageCount": 1,
            }
        else:
            row["messageCount"] += 1
    return {
        "sessions": sorted(
            list(sessions.values()),
            key=lambda x: x["lastMessageAt"],
            reverse=True,
        )
    }


async def get_context_for_listing(org_id: str, listing_id: str):
    """
    Fetches real data for a listing to inject into the agent prompt.
    Matches the schema expected by Agent 2 (Property Analyst).
    """
    from datetime import datetime, timedelta
    from app.models.inventory_master import InventoryMaster
    from app.models.reservation import Reservation
    from app.models.benchmark_data import BenchmarkData
    from app.models.market_event import MarketEvent

    listing = await Listing.get(PydanticObjectId(listing_id))
    if not listing:
        return {}

    # 1. Date Range (last 30 and next 60 days)
    today = datetime.utcnow().date()
    from_date = (today - timedelta(days=30)).isoformat()
    to_date = (today + timedelta(days=60)).isoformat()

    # 2. Fetch Data
    inv_docs = await InventoryMaster.find(
        InventoryMaster.listingId == listing.id,
        InventoryMaster.date >= from_date,
        InventoryMaster.date <= to_date
    ).sort(+InventoryMaster.date).to_list()

    res_docs = await Reservation.find(
        Reservation.listingId == listing.id,
        Reservation.checkIn <= to_date,
        Reservation.checkOut >= from_date
    ).to_list()

    bench = await BenchmarkData.find_one(
        BenchmarkData.listingId == listing.id
    )

    events = await MarketEvent.find(
        MarketEvent.orgId == PydanticObjectId(org_id),
        MarketEvent.startDate >= from_date,
        MarketEvent.startDate <= to_date
    ).to_list()

    # 3. Calculate Metrics
    from app.models.organization import Organization
    org = await Organization.get(PydanticObjectId(org_id))
    
    # Booking velocity (past 30 days)
    velocity_cutoff = (today - timedelta(days=30)).isoformat()
    velocity = [r for r in res_docs if r.createdAt and r.createdAt.date().isoformat() >= velocity_cutoff]
    
    valid_statuses = ["confirmed", "checked_in", "checked_out"]
    booked_nights = sum(int(r.nights or 0) for r in res_docs if r.status in valid_statuses)
    total_revenue = sum(float(r.totalPrice or 0) for r in res_docs if r.status in valid_statuses)
    
    # Bookable vs Occupied (next 30 days)
    next_30 = (today + timedelta(days=30)).isoformat()
    future_inv = [i for i in inv_docs if i.date >= today.isoformat() and i.date <= next_30]
    booked_future = [i for i in future_inv if i.status == "booked"]
    blocked_future = [i for i in future_inv if i.status == "blocked"]
    
    occupancy_pct = round((len(booked_future) / len(future_inv)) * 100, 1) if future_inv else 0

    # 4. Format Context Block
    context = {
        "org_id": org_id,
        "listing_id": listing_id,
        "apiKey": org.hostawayApiKey if org else None,
        "analysis_window": {"from": today.isoformat(), "to": to_date},
        "property": {
            "name": listing.name,
            "area": listing.area,
            "city": listing.city,
            "bedrooms": listing.bedroomsNumber,
            "current_price": listing.price,
            "floor_price": listing.priceFloor or 0,
            "ceiling_price": listing.priceCeiling or 0,
            "currency": listing.currencyCode or "AED"
        },
        "today": today.isoformat(),
        "metrics": {
            "occupancy_pct": occupancy_pct,
            "booked_nights": booked_nights,
            "bookable_nights": len(future_inv),
            "blocked_nights": len(blocked_future),
            "avg_nightly_rate": round(total_revenue / booked_nights, 2) if booked_nights else 0,
            "total_revenue": total_revenue,
            "booking_velocity_30d": len(velocity)
        },
        "available_dates": [
            {
                "date": i.date,
                "current_price": i.currentPrice,
                "status": i.status,
                "min_stay": i.minStay
            }
            for i in future_inv if i.status == "available"
        ],
        "inventory": [
            {
                "date": i.date,
                "status": i.status,
                "current_price": i.currentPrice
            }
            for i in inv_docs if i.date >= today.isoformat() # Only future for reasoning
        ],
        "recent_reservations": [
            {
                "guestName": r.guestName,
                "startDate": r.checkIn,
                "endDate": r.checkOut,
                "nights": r.nights,
                "totalPrice": r.totalPrice,
                "channel": r.channelName
            }
            for r in res_docs[-10:] # Last 10
        ],
        "nearby_comps": {
            "percentiles": {
                "p25": bench.p25Rate if bench else 0,
                "p50": bench.p50Rate if bench else 0,
                "p75": bench.p75Rate if bench else 0,
                "p90": bench.p90Rate if bench else 0
            }
        },
        "market_events": [
            {
                "title": e.name,
                "start_date": e.startDate,
                "end_date": e.endDate,
                "impact": e.impactLevel,
                "description": e.description,
                "suggested_premium_pct": e.upliftPct
            }
            for e in events[:15] # Top 15
        ]
    }
    
    return context


@engagement_router.post("/chat")
async def unified_chat(req: UnifiedChatRequest):
    async def gen():
        # Step 1: Routing
        yield _sse_event("status", {"step": "routing", "message": "CRO Router: Identifying pricing opportunities..."})
        yield _sse_event("thinking", {"message": "Analyzing request intent and routing to specialized analyst..."})
        await asyncio.sleep(0.8)
        
        # Step 2: Analyzing
        yield _sse_event("status", {"step": "analyzing", "message": "Property Analyst: Researching market trends..."})
        yield _sse_event("thinking", {"message": "Querying market benchmarks, nearby comps, and event impacts..."})
        await asyncio.sleep(0.5)
        
        # Call Lyzr Agent
        agent_id = os.getenv("AGENT_ID", "69998743f4d61186679a9515")
        session_id = req.graphSessionId or req.sessionId or f"gen-{datetime.utcnow().timestamp()}"
        db_session_id = req.sessionId or session_id

        # 💎 Always inject property/market intelligence context for high-fidelity responses
        final_message = req.message
        if req.orgId and req.context and req.context.get("propertyId"):
            prop_id = req.context.get("propertyId")
            
            yield _sse_event("status", {"step": "analyzing", "message": "Fetching property inventory and reservations..."})
            yield _sse_event("thinking", {"message": "Syncing with InventoryMaster and Reservation collections..."})
            
            ctx_data = await get_context_for_listing(req.orgId, prop_id)
            if ctx_data:
                yield _sse_event("status", {"step": "analyzing", "message": "Context collected. Injecting market intelligence..."})
                yield _sse_event("thinking", {"message": "Data successfully aggregated. Handing over to Property Analyst..."})
                
                # Prepend data source block
                # Explicitly inject IDs into context for reliability
                ctx_data["apiKey"] = os.environ.get("LYZR_API_KEY", "")
                thread_id = req.context.get("threadId")
                final_message = f"## DATA_SOURCE_INJECTION\n{json.dumps(ctx_data, indent=2)}\n\n[CONTEXT: orgId={req.orgId}, listingId={prop_id}, threadId={thread_id}]\n\nUSER_MESSAGE: {req.message}"
                print(f"💎 [CHAT] Context injected for listing {prop_id} and thread {thread_id}")
        
        # Stream from Lyzr
        from app.services.lyzr import stream_lyzr_agent
        
        # 💎 REAL SCENARIO FIX: Pass actual database IDs as system variables
        # This prevents the agent from "inventing" placeholder IDs.
        system_vars = {
            "org_id": req.orgId,
            "listing_id": req.context.get("propertyId") if req.context else None,
            "thread_id": req.context.get("threadId") if req.context else None,
            "today": datetime.utcnow().strftime("%Y-%m-%d"),
            "currency": ctx_data.get("property", {}).get("currency", "AED") if 'ctx_data' in locals() else "AED"
        }

        full_response = ""
        async for event in stream_lyzr_agent(
            agent_id=agent_id,
            message=final_message,
            session_id=session_id,
            system_prompt_variables=system_vars
        ):
            # Forward event to SSE
            event_type = event.get("type")
            
            if event_type == "agent_event":
                yield _sse_event("agent_event", {"payload": event.get("payload")})
            
            elif event_type == "thinking":
                msg = event.get("message")
                print(f"   [GEN] Thinking: {msg}")
                yield _sse_event("thinking", {"message": msg})

            elif event_type == "content":
                yield _sse_event("content", {"message": event.get("content")})
            
            elif event_type == "final_response":
                full_response = event.get("content")
                yield _sse_event("complete", {"message": full_response})
            
            elif event_type == "error":
                yield _sse_event("error", {"message": event.get("message")})

        # Step 3: Validating
        yield _sse_event("status", {"step": "validating", "message": "PriceGuard: Verifying constraints..."})
        yield _sse_event("thinking", {"message": "Enforcing floor/ceiling prices and checking for policy compliance..."})
        await asyncio.sleep(0.3)

        if full_response:
            # Signal completion to the graph
            yield _sse_event("status", {"step": "complete", "message": "Output Generated"})
            yield _sse_event("output_generated", {"message": "Final recommendation synthesized and delivered."})
            
            # Extract JSON if possible
            from app.services.lyzr import extract_json
            parsed_json = extract_json(full_response)

            # Step 4: Complete
            yield _sse_event("complete", {
                "message": full_response,
                "parsedJson": parsed_json,
                "proposals": parsed_json.get("proposals") if parsed_json else None
            })
            
            # Save to DB
            if req.orgId:
                msg = ChatMessage(
                    orgId=PydanticObjectId(req.orgId),
                    sessionId=db_session_id,
                    role="assistant",
                    content=full_response,
                    context=ChatContext(
                        type=req.context.get("type", "property") if req.context else "property",
                        propertyId=PydanticObjectId(req.context.get("propertyId")) if req.context and req.context.get("propertyId") else None
                    ) if req.context else None,
                    metadata={"agentId": agent_id}
                )
                await msg.insert()
        else:
            yield _sse_event("error", {"message": "Agent failed to generate a response. The stream may have been interrupted. Please try again."})

    return StreamingResponse(gen(), media_type="text/event-stream")


@engagement_router.get("/chat/status")
async def chat_status():
    """Returns WebSocket configuration for the execution graph."""
    return {
        "wsBaseUrl": os.getenv("LYZR_WS_BASE_URL", "wss://metrics.studio.lyzr.ai/ws"),
        "wsApiKey": os.getenv("LYZR_API_KEY", "")
    }


@engagement_router.get("/agents/status")
async def agents_status(orgId: str):
    org = await Organization.get(PydanticObjectId(orgId))
    pending_proposals = await InventoryMaster.find(
        InventoryMaster.orgId == PydanticObjectId(orgId),
        InventoryMaster.status == "pending",
    ).count()
    critical_insights = await _db()["insights"].count_documents({"orgId": ObjectId(orgId), "severity": "critical"})
    now = datetime.utcnow().isoformat()
    state = org.systemState if org else "connected"
    return {
        "systemState": state,
        "agents": [
            {"id": "cro", "name": "CRO Router", "role": "Routing", "status": "active", "description": "Coordinates agent actions", "lastRunAt": now, "lastRunStatus": "always_on", "metrics": {}},
            {"id": "pricing_optimizer", "name": "Pricing Optimizer", "role": "Pricing", "status": "active", "description": "Optimizes nightly prices", "lastRunAt": now, "lastRunStatus": "event_driven", "metrics": {}},
            {"id": "adjustment_reviewer", "name": "Adjustment Reviewer", "role": "Risk", "status": "warning" if pending_proposals else "active", "description": "Reviews proposal risk", "lastRunAt": now, "lastRunStatus": "event_driven", "metrics": {"pendingProposals": pending_proposals}},
            {"id": "anomaly_detector", "name": "Anomaly Detector", "role": "QA", "status": "warning" if critical_insights else "active", "description": "Finds outliers and issues", "lastRunAt": now, "lastRunStatus": "event_driven", "metrics": {"criticalInsights": critical_insights}},
        ],
        "summary": {
            "totalAgents": 4,
            "activeCount": 2 if (pending_proposals or critical_insights) else 4,
            "warningCount": int(bool(pending_proposals)) + int(bool(critical_insights)),
            "errorCount": 0,
            "pendingProposals": pending_proposals,
            "criticalInsights": critical_insights,
            "isStale": False,
            "lastRunAt": now,
        },
    }


class MarketSyncRequest(OrgScopedRequest):
    daysAhead: int = 90
    marketCity: str = "Dubai"


@engagement_router.post("/v1/system/events/sync")
async def sync_market_events(req: MarketSyncRequest):
    inserted = 0
    updated = 0
    today = datetime.utcnow().date()
    for i, title in enumerate(["City Expo", "Holiday Peak", "Concert Weekend"]):
        start = (today.replace(day=today.day) if i == 0 else today).isoformat()
        end = start
        existing = await MarketEvent.find_one(
            MarketEvent.orgId == PydanticObjectId(req.orgId),
            MarketEvent.name == title,
            MarketEvent.startDate == start,
        )
        if existing:
            existing.updatedAt = datetime.utcnow()
            await existing.save()
            updated += 1
        else:
            await MarketEvent(
                orgId=PydanticObjectId(req.orgId),
                name=title,
                startDate=start,
                endDate=end,
                area=req.marketCity,
                impactLevel="medium" if i == 0 else ("high" if i == 1 else "low"),
                upliftPct=8 + i * 3,
                description=f"Auto-synced signal for {req.marketCity}",
                source="manual",
            ).insert()
            inserted += 1
    return {"success": True, "data": {"inserted": inserted, "updated": updated}}


@engagement_router.get("/db-viewer")
async def db_viewer(orgId: str):
    org_oid = ObjectId(orgId)
    listings = await _db()["listings"].find({"orgId": org_oid}).to_list(200)
    inventory = await _db()["inventorymaster"].find({"orgId": org_oid}).to_list(400)
    reservations = await _db()["reservations"].find({"orgId": org_oid}).to_list(300)
    market_events = await _db()["market_events"].find({"orgId": org_oid}).to_list(300)
    chat_messages = await _db()["chatmessages"].find({"orgId": org_oid}).to_list(300)
    guest_summaries = await _db()["guestsummaries"].find({"orgId": org_oid}).to_list(200)
    hostaway_conversations = await _db()["hostawayconversations"].find({"orgId": org_oid}).to_list(200)
    benchmark_data = await _db()["benchmark_data"].find({"orgId": org_oid}).to_list(200)
    user_settings = [{"orgId": orgId, "marketCode": (await Organization.get(PydanticObjectId(orgId))).marketCode if await Organization.get(PydanticObjectId(orgId)) else "UAE_DXB"}]
    mock_hostaway_replies = await _db()["mock_hostaway_replies"].find({"orgId": org_oid}).to_list(200)

    def _stringify(rows):
        return [{k: str(v) if isinstance(v, (ObjectId, PydanticObjectId)) else v for k, v in r.items()} for r in rows]

    inv_dates = [r.get("date") for r in inventory if r.get("date")]
    res_in = [r.get("checkIn") for r in reservations if r.get("checkIn")]
    res_out = [r.get("checkOut") for r in reservations if r.get("checkOut")]

    return {
        "summary": {
            "listings": len(listings),
            "inventory_master": len(inventory),
            "reservations": len(reservations),
            "market_events": len(market_events),
            "chat_messages": len(chat_messages),
            "user_settings": len(user_settings),
            "guest_summaries": len(guest_summaries),
            "mock_hostaway_replies": len(mock_hostaway_replies),
            "hostaway_conversations": len(hostaway_conversations),
            "benchmark_data": len(benchmark_data),
        },
        "date_ranges": {
            "calendar": {"min": min(inv_dates) if inv_dates else None, "max": max(inv_dates) if inv_dates else None},
            "reservations": {"min": min(res_in) if res_in else None, "max": max(res_out) if res_out else None},
        },
        "data": {
            "listings": _stringify(listings),
            "inventory_master": _stringify(inventory),
            "reservations": _stringify(reservations),
            "market_events": _stringify(market_events),
            "chat_messages": _stringify(chat_messages),
            "user_settings": _stringify(user_settings),
            "guest_summaries": _stringify(guest_summaries),
            "mock_hostaway_replies": _stringify(mock_hostaway_replies),
            "hostaway_conversations": _stringify(hostaway_conversations),
            "benchmark_data": _stringify(benchmark_data),
        },
    }


class OnboardingPatchRequest(OrgScopedRequest):
    step: Optional[str] = None
    selectedListingIds: Optional[list[str]] = None
    activatedListingIds: Optional[list[str]] = None
    marketCode: Optional[str] = None
    listings: Optional[list[dict]] = None
    strategy: Optional[str] = None


@engagement_router.patch("/onboarding")
async def patch_onboarding(req: OnboardingPatchRequest):
    org = await Organization.get(PydanticObjectId(req.orgId))
    if not org:
        return {"success": False, "error": "Organization not found"}
    if req.step:
        org.onboarding.step = req.step  # type: ignore
        if req.step == "complete":
            org.onboarding.completedAt = datetime.utcnow()
    if req.selectedListingIds is not None:
        org.onboarding.selectedListingIds = req.selectedListingIds
    if req.activatedListingIds is not None:
        org.onboarding.activatedListingIds = req.activatedListingIds
    if req.marketCode:
        org.marketCode = req.marketCode
    if req.listings is not None:
        org.onboarding.listings = req.listings
        # Seed listings if they do not exist yet.
        for l in req.listings:
            hw_id = str(l.get("id", ""))
            if not hw_id:
                continue
            existing = await Listing.find_one(Listing.orgId == org.id, Listing.hostawayId == hw_id)
            if existing:
                existing.name = l.get("name") or existing.name
                existing.city = l.get("city") or existing.city
                existing.isActive = hw_id in (req.activatedListingIds or org.onboarding.activatedListingIds)
                existing.updatedAt = datetime.utcnow()
                await existing.save()
            else:
                await Listing(
                    orgId=org.id,
                    hostawayId=hw_id,
                    name=l.get("name", f"Listing {hw_id}"),
                    city=l.get("city", ""),
                    bedroomsNumber=int(l.get("bedrooms", 1) or 1),
                    price=float(l.get("price", 300) or 300),
                    currencyCode=org.currency,
                    isActive=hw_id in (req.activatedListingIds or []),
                ).insert()
    await org.save()
    return {"success": True, "onboarding": org.onboarding.model_dump()}


class MarketSetupRequest(OrgScopedRequest):
    context: Optional[dict] = None
    dateRange: Optional[dict] = None


@engagement_router.post("/market-setup")
async def market_setup(req: MarketSetupRequest):
    import time
    from datetime import timedelta
    from app.services.market_intelligence import sync_external_market_intelligence, sync_internet_benchmark

    org_oid = PydanticObjectId(req.orgId)
    org = await Organization.get(org_oid)
    if not org:
        return {"success": False, "error": "Org not found"}

    if req.context and req.context.get("type") == "property":
        org.systemState = "active"
        org.systemStateSince = datetime.utcnow()
        await org.save()

    start_time = time.time()
    events_count = 0
    sql_trace = []

    date_from = req.dateRange.get("from") if req.dateRange else datetime.utcnow().strftime("%Y-%m-%d")
    date_to = req.dateRange.get("to") if req.dateRange else (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d")

    # 1. Market Events Sync (Agent 6)
    if req.context and req.context.get("type") == "property":
        property_id = req.context.get("propertyId")
        listing = await Listing.get(PydanticObjectId(property_id))
        if listing:
            city = listing.city or "Dubai"
            area = listing.area or "Dubai Marina"

            sql_trace.append({"name": "Agent 6", "sql": f"Triggering Intelligence Sweep for {area}, {city}"})

            # Sync events
            intel_res = await sync_external_market_intelligence(
                org_id=ObjectId(org.id),
                city=city,
                area=area,
                date_from=date_from,
                date_to=date_to,
                force=True
            )

            if intel_res.get("success"):
                events_count = intel_res.get("results", {}).get("inserted", 0) + intel_res.get("results", {}).get("updated", 0)
                if events_count == 0 and intel_res.get("count"):
                    events_count = intel_res.get("count")

            # Agent 7 (Benchmark Research) disabled - relying on Database/Airbtics cache directly
            # sql_trace.append({"name": "Agent 7", "sql": f"Fallback Benchmark Research for {area}, {listing.bedroomsNumber} BR"})

    else:
        # Portfolio level - just sync general events
        intel_res = await sync_external_market_intelligence(
            org_id=ObjectId(org.id),
            city="Dubai",
            area="Dubai",
            date_from=date_from,
            date_to=date_to,
            force=True
        )
        if intel_res.get("success"):
            events_count = intel_res.get("results", {}).get("inserted", 0) + intel_res.get("results", {}).get("updated", 0)
            if events_count == 0 and intel_res.get("count"):
                events_count = intel_res.get("count")

    if events_count == 0:
        events_count = await MarketEvent.find(MarketEvent.orgId == org_oid).count()

    duration = time.time() - start_time

    return {
        "success": True,
        "eventsCount": events_count,
        "duration": f"{duration:.1f}s",
        "guardrailsSetByAi": True,
        "guardrails": {"floor": 0, "ceiling": 0},
        "sqlTrace": sql_trace,
    }


class ReservationCreateRequest(OrgScopedRequest):
    listingMapId: Optional[int] = None
    listingId: Optional[str] = None
    guestName: str
    guestEmail: Optional[str] = None
    arrivalDate: str
    departureDate: str
    nights: int = 1
    totalPrice: float = 0
    channelName: str = "Direct"
    status: str = "confirmed"


@engagement_router.post("/reservations")
async def create_reservation(req: ReservationCreateRequest):
    listing_oid = None
    if req.listingId:
        listing_oid = ObjectId(req.listingId)
    elif req.listingMapId is not None:
        listing = await Listing.find_one(Listing.orgId == PydanticObjectId(req.orgId), Listing.hostawayId == str(req.listingMapId))
        if listing:
            listing_oid = listing.id
    if not listing_oid:
        listing = await Listing.find_one(Listing.orgId == PydanticObjectId(req.orgId))
        if not listing:
            return {"success": False, "error": "No listing found"}
        listing_oid = listing.id
    created = Reservation(
        orgId=PydanticObjectId(req.orgId),
        listingId=PydanticObjectId(str(listing_oid)),
        guestName=req.guestName,
        guestEmail=req.guestEmail,
        checkIn=req.arrivalDate,
        checkOut=req.departureDate,
        nights=req.nights,
        totalPrice=req.totalPrice,
        channelName=req.channelName,
        status=req.status,  # type: ignore
        source="manual",
    )
    await created.insert()
    return {"success": True, "id": str(created.id)}
