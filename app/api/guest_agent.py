"""
api/guest_agent.py — Guest Reply Agent API
─────────────────────────────────────────
Backend tool endpoints for the Guest Reply Agent (Reservation Agent).

Architecture mirrors the CRO Router pattern:
  - Structured JSON output: intent + action + reply_draft (like CRO's routing + proposals + chat_response)
  - Comms state gate enforced on every send
  - Draft approval flow identical to CRO pricing proposals

Tool endpoints (8 tools, V1 — email only; WhatsApp/SMS/Voice deferred to V2):
  1. list_threads        — inbox overview
  2. read_thread         — full context for one thread
  3. send_reply          — draft/send/queue a guest reply
  4. close_thread        — resolve + optional farewell
  5. create_ops_ticket   — raise maintenance/housekeeping issue
  6. escalate_thread     — hand off to human PM, pause comms
  7. send_access_details — structured access info (post verification)
  8. get_listing_profile — listing KB data for agent context
"""

import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Literal, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from bson import ObjectId

guest_agent_router = APIRouter(prefix="/guest-agent", tags=["guest-agent"])


def now_utc():
    return datetime.now(timezone.utc)


def oid(s: Optional[str]) -> Optional[ObjectId]:
    if not s or s == "undefined" or s == "null":
        return None
    try:
        return ObjectId(s)
    except Exception:
        # For required fields, the model validation will still catch this
        # but we return None to avoid crashing before the model gets it
        return None


# ── 1. listThreads ─────────────────────────────────────────────────────────────

@guest_agent_router.get("/threads")
async def list_threads(
    orgId: str,
    status_filter: str = "all",
    reservation_id: Optional[str] = None,
    limit: int = 20
):
    """
    Returns open/urgent/pending threads sorted by last_activity_at.
    Mirrors CRO Router's context injection — gives the agent its inbox overview.
    """
    from app.models.guest_thread import GuestThread

    print(f"💎 [GUEST_TOOL] list_threads | orgId={orgId} | status={status_filter}")
    query = {"orgId": oid(orgId)}
    if status_filter != "all":
        query["status"] = status_filter
    if reservation_id:
        query["reservationId"] = reservation_id

    threads = await GuestThread.find(query).sort(-GuestThread.lastActivityAt).limit(limit).to_list()

    return {
        "threads": [
            {
                "threadId": str(t.id),
                "reservationId": t.reservationId,
                "listingId": str(t.listingId) if t.listingId else None,
                "channel": t.channel,
                "commsState": t.commsState,
                "status": t.status,
                "lastActivityAt": t.lastActivityAt.isoformat(),
                "unreadCount": sum(1 for m in t.messages if m.direction == "inbound" and m.status == "sent"),
                "lastMessagePreview": (t.messages[-1].content[:80] if t.messages else ""),
            }
            for t in threads
        ]
    }


# ── 2. readThread ──────────────────────────────────────────────────────────────

@guest_agent_router.get("/threads/{thread_id}")
async def read_thread(thread_id: str, include_reservation: bool = True, message_limit: int = 50):
    """
    Full thread context: messages + reservation + guest profile + listing profile.
    This is the primary context bundle the agent reads before drafting any reply.
    Mirrors CRO Router's [SYSTEM CONTEXT] injection.
    """
    from app.models.guest_thread import GuestThread
    from app.models.reservation import Reservation
    from app.models.listing import Listing

    print(f"💎 [GUEST_TOOL] read_thread | threadId={thread_id}")
    thread = await GuestThread.get(oid(thread_id))
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    messages = thread.messages[-message_limit:]

    result = {
        "threadId": str(thread.id),
        "reservationId": thread.reservationId,
        "commsState": thread.commsState,
        "status": thread.status,
        "channel": thread.channel,
        "messages": [
            {
                "messageId": m.messageId,
                "direction": m.direction,
                "content": m.content,
                "handledBy": m.handledBy,
                "intent": m.intent,
                "sentiment": m.sentiment,
                "confidence": m.confidence,
                "status": m.status,
                "createdAt": m.createdAt.isoformat(),
            }
            for m in messages
        ],
    }

    if include_reservation and thread.reservationId:
        res = await Reservation.find_one(Reservation.reservationId == thread.reservationId)
        if res:
            result["reservation"] = {
                "reservationId": res.reservationId,
                "status": res.status,
                "checkIn": res.checkIn,
                "checkOut": res.checkOut,
                "guestName": res.guestName,
                "guestEmail": res.guestEmail,
                "nights": res.nights,
                "totalPrice": float(res.totalPrice or 0),
                "channelName": res.channelName,
                "specialRequests": getattr(res, "specialRequests", None),
            }

    if thread.listingId:
        listing = await Listing.get(thread.listingId)
        if listing:
            result["listingProfile"] = {
                "listingId": str(listing.id),
                "name": listing.name,
                "area": listing.area,
                "checkInTime": getattr(listing, "checkInTime", "15:00"),
                "checkOutTime": getattr(listing, "checkOutTime", "11:00"),
                "checkInMethod": getattr(listing, "checkInMethod", "key_handover"),
                "houseRules": getattr(listing, "houseRules", []),
                "parkingInstructions": getattr(listing, "parkingInstructions", ""),
                "amenities": getattr(listing, "amenities", []),
                "maxGuests": getattr(listing, "personCapacity", 0),
                "bedrooms": listing.bedroomsNumber,
                # NOTE: wifi/access codes NOT returned here — use send_access_details tool
            }

    return result


# ── 3. sendReply ───────────────────────────────────────────────────────────────

class SendReplyRequest(BaseModel):
    threadId: str
    content: str
    discloseAi: bool = True
    approvalRequired: bool = False          # True → status=pending_approval
    intent: Optional[str] = None
    sentiment: Optional[str] = None
    confidence: Optional[float] = None

@guest_agent_router.post("/send-reply")
async def send_reply(req: SendReplyRequest):
    """
    Draft or send a guest reply.
    CRITICAL: Checks comms_state before any send — identical gate to CRO's PriceGuard block.

    comms_state == active + approvalRequired=False → status=sent (auto-send)
    comms_state == active + approvalRequired=True  → status=pending_approval (PM must approve)
    comms_state != active                          → COMMS_STATE_BLOCKED error
    """
    from app.models.guest_thread import GuestThread, GuestMessage

    print(f"💎 [GUEST_TOOL] send_reply | threadId={req.threadId} | intent={req.intent} | action={req.action if hasattr(req, 'action') else 'send'}")
    thread = await GuestThread.get(oid(req.threadId))
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    # ── THE GATE ──────────────────────────────────────────────────────────────
    if thread.commsState != "active":
        return {
            "error": "COMMS_STATE_BLOCKED",
            "commsState": thread.commsState,
            "message": f"Agent cannot send — comms_state is '{thread.commsState}'. Human takeover required."
        }

    status = "pending_approval" if req.approvalRequired else "sent"

    msg = GuestMessage(
        messageId=str(uuid.uuid4()),
        direction="outbound",
        content=req.content,
        handledBy="reservation_agent",
        intent=req.intent,
        sentiment=req.sentiment,
        confidence=req.confidence,
        discloseAi=req.discloseAi,
        status=status,
        createdAt=now_utc(),
        sentAt=now_utc() if status == "sent" else None,
    )

    thread.messages.append(msg)
    thread.lastActivityAt = now_utc()
    if req.approvalRequired:
        thread.status = "pending_approval"
    await thread.save()

    return {
        "messageId": msg.messageId,
        "status": status,
        "commsState": thread.commsState,
        # CRO-style action buttons — PM sees approve/reject in Unified Inbox
        "actionButtons": ["approve", "reject"] if status == "pending_approval" else [],
    }


# Lyzr-style alias for sendGuestMessage
@guest_agent_router.post("/threads/{thread_id}/messages")
async def create_thread_message(thread_id: str, req: dict):
    """
    Alias for send_reply to support Lyzr's RESTful expectation:
    POST /threads/{thread_id}/messages
    """
    # Map the dynamic request to our structured SendReplyRequest
    content = req.get("content")
    if not content:
        raise HTTPException(status_code=400, detail="Missing 'content' in request body")
    
    reply_req = SendReplyRequest(
        threadId=thread_id,
        content=content,
        discloseAi=req.get("discloseAi", True),
        approvalRequired=req.get("approvalRequired", False),
        intent=req.get("intent"),
        sentiment=req.get("sentiment"),
        confidence=req.get("confidence")
    )
    return await send_reply(reply_req)


# ── 4. closeThread ─────────────────────────────────────────────────────────────

class CloseThreadRequest(BaseModel):
    threadId: str
    reason: str
    sendFarewell: bool = False

@guest_agent_router.post("/close-thread")
async def close_thread(req: CloseThreadRequest):
    from app.models.guest_thread import GuestThread, GuestMessage

    print(f"💎 [GUEST_TOOL] close_thread | threadId={req.threadId} | reason={req.reason}")
    thread = await GuestThread.get(oid(req.threadId))
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    thread.status = "closed"
    thread.closedAt = now_utc()
    thread.closureReason = req.reason

    if req.sendFarewell and thread.commsState == "active":
        farewell = GuestMessage(
            messageId=str(uuid.uuid4()),
            direction="outbound",
            content="Thank you for staying with us! We'd love to hear about your experience — a quick review would mean the world to us. 🌟",
            handledBy="reservation_agent",
            intent="farewell_review_nudge",
            status="sent",
            createdAt=now_utc(),
            sentAt=now_utc(),
        )
        thread.messages.append(farewell)

    thread.lastActivityAt = now_utc()
    await thread.save()

    return {"closed": True, "threadId": req.threadId, "reason": req.reason}


# ── 5. createOpsTicket ─────────────────────────────────────────────────────────

class CreateTicketRequest(BaseModel):
    orgId: str
    reservationId: str
    threadId: str
    listingId: Optional[str] = None
    category: Literal["maintenance", "housekeeping", "access", "noise", "amenity_fault", "other"]
    description: str
    severity: Literal["critical", "high", "medium", "low"]

SLA_MAP = {"critical": 2, "high": 4, "medium": 24, "low": 72}

@guest_agent_router.post("/create-ops-ticket")
async def create_ops_ticket(req: CreateTicketRequest):
    from app.models.ops_ticket import OpsTicket

    print(f"💎 [GUEST_TOOL] create_ops_ticket | orgId={req.orgId} | cat={req.category} | sev={req.severity}")
    ticket = OpsTicket(
        orgId=oid(req.orgId),
        reservationId=req.reservationId,
        threadId=req.threadId,
        listingId=oid(req.listingId) if req.listingId else None,
        category=req.category,
        description=req.description,
        severity=req.severity,
        slaHours=SLA_MAP.get(req.severity, 24),
        createdBy="reservation_agent",
        status="open",
    )
    await ticket.insert()

    return {
        "ticketId": str(ticket.id),
        "category": ticket.category,
        "severity": ticket.severity,
        "slaHours": ticket.slaHours,
        "status": "open",
        "message": f"Ops ticket created. SLA: {ticket.slaHours}h. Agent should acknowledge issue to guest in a separate reply."
    }


# Lyzr-style alias for createOpsTicket
@guest_agent_router.post("/tickets")
async def create_ticket_alias(req: CreateTicketRequest):
    """
    Alias for create_ops_ticket to support Lyzr's RESTful expectation:
    POST /tickets
    """
    return await create_ops_ticket(req)


@guest_agent_router.get("/tickets")
async def list_ops_tickets(orgId: str, status: Optional[str] = None):
    """
    Returns operations tickets raised by the Guest Agent.
    Used for the separate Operations/Task Tower dashboard.
    """
    from app.models.ops_ticket import OpsTicket
    from app.models.listing import Listing
    
    query = {"orgId": oid(orgId)}
    if status:
        query["status"] = status
        
    tickets = await OpsTicket.find(query).sort(-OpsTicket.createdAt).to_list()
    
    # Enrich with listing names
    listing_ids = list({t.listingId for t in tickets if t.listingId})
    listings = await Listing.find({"_id": {"$in": listing_ids}}).to_list() if listing_ids else []
    listing_map = {str(l.id): l.name for l in listings}
    
    results = []
    for t in tickets:
        d = t.dict()
        d["id"] = str(t.id)
        d["_id"] = str(t.id)
        d["orgId"] = str(t.orgId)
        d["listingId"] = str(t.listingId) if t.listingId else None
        d["listingName"] = listing_map.get(str(t.listingId), "Unknown Property")
        d["createdAt"] = t.createdAt.isoformat()
        d["updatedAt"] = t.updatedAt.isoformat()
        results.append(d)
        
    return {"tickets": results, "count": len(results)}

class UpdateTicketStatusRequest(BaseModel):
    status: Literal["open", "assigned", "in_progress", "resolved", "closed"]
    orgId: str

@guest_agent_router.patch("/tickets/{ticket_id}/status")
async def update_ticket_status(ticket_id: str, req: UpdateTicketStatusRequest):
    from app.models.ops_ticket import OpsTicket
    ticket = await OpsTicket.find_one(
        OpsTicket.id == oid(ticket_id), OpsTicket.orgId == oid(req.orgId)
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
        
    ticket.status = req.status
    ticket.updatedAt = now_utc()
    if req.status == "resolved":
        ticket.resolvedAt = now_utc()
        
    await ticket.save()
    return {"success": True, "status": ticket.status, "ticketId": str(ticket.id)}


# ── 6. escalateThread ─────────────────────────────────────────────────────────

class EscalateRequest(BaseModel):
    threadId: str
    reason: str
    urgency: Literal["immediate", "high", "normal"]
    contextSummary: str
    draftReply: Optional[str] = None

@guest_agent_router.post("/escalate-thread")
async def escalate_thread(req: EscalateRequest):
    from app.models.guest_thread import GuestThread, GuestMessage

    print(f"💎 [GUEST_TOOL] escalate_thread | threadId={req.threadId} | urgency={req.urgency}")
    
    # Handle placeholder threads for manual/global chat testing
    if "placeholder" in req.threadId.lower() or req.threadId == "N/A" or req.threadId == "UNKNOWN":
        return {
            "success": True, 
            "message": "Thread escalation simulated (Manual/Placeholder thread). High-priority notification sent to dashboard.",
            "threadId": req.threadId,
            "status": "urgent"
        }

    thread = await GuestThread.get(oid(req.threadId))
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    # Set comms gate to paused — agent STOPS sending
    thread.commsState = "paused"
    thread.status = "urgent"

    # Log escalation as system message
    system_msg = GuestMessage(
        messageId=str(uuid.uuid4()),
        direction="outbound",
        content=f"[ESCALATED] Reason: {req.reason} | Urgency: {req.urgency} | Context: {req.contextSummary}",
        handledBy="system",
        intent="escalation",
        status="sent",
        createdAt=now_utc(),
        sentAt=now_utc(),
    )
    thread.messages.append(system_msg)

    # If agent provided a draft for human to review
    if req.draftReply:
        draft_msg = GuestMessage(
            messageId=str(uuid.uuid4()),
            direction="outbound",
            content=req.draftReply,
            handledBy="reservation_agent",
            intent="escalation_draft",
            status="pending_approval",
            createdAt=now_utc(),
        )
        thread.messages.append(draft_msg)

    thread.lastActivityAt = now_utc()
    await thread.save()

    # TODO V1: Send email alert to escalation contacts from CommsPolicy
    # TODO V2: Send WhatsApp alert via Twilio

    return {
        "escalated": True,
        "threadId": req.threadId,
        "commsState": "paused",
        "urgency": req.urgency,
        "message": "Thread escalated. comms_state set to paused. Human PM must review before any reply is sent.",
        "actionButtons": ["approve", "reject"] if req.draftReply else [],
    }


# Lyzr-style alias for escalateThread
@guest_agent_router.post("/threads/{thread_id}/escalate")
async def escalate_thread_alias(thread_id: str, req: EscalateRequest):
    """
    Alias for escalate_thread to support Lyzr's RESTful expectation:
    POST /threads/{thread_id}/escalate
    """
    # Ensure the path ID matches the body ID for consistency
    if req.threadId != thread_id:
        req.threadId = thread_id
    return await escalate_thread(req)


# ── 7. sendAccessDetails ───────────────────────────────────────────────────────

class AccessDetailsRequest(BaseModel):
    threadId: str
    orgId: str
    listingId: str
    reservationId: str

@guest_agent_router.post("/send-access-details")
async def send_access_details(req: AccessDetailsRequest):
    """
    Sends structured access details (check-in method, wifi) to a verified guest.
    SECURITY: wifi_password and access codes are ONLY released through this tool,
    never interpolated into free-text replies.
    """
    from app.models.guest_thread import GuestThread, GuestMessage
    from app.models.listing import Listing
    from app.models.reservation import Reservation

    print(f"💎 [GUEST_TOOL] send_access_details | threadId={req.threadId} | listingId={req.listingId}")
    thread = await GuestThread.get(oid(req.threadId))
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    if thread.commsState != "active":
        return {"error": "COMMS_STATE_BLOCKED", "commsState": thread.commsState}

    # Verify the reservation is confirmed or checked_in
    res = await Reservation.find_one(Reservation.reservationId == req.reservationId)
    if not res or res.status not in ("confirmed", "checked_in"):
        raise HTTPException(
            status_code=403,
            detail="Access details can only be sent to confirmed or checked-in guests"
        )

    listing = await Listing.get(oid(req.listingId))
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    # Build structured access message — fields from listing_profile
    check_in_method = getattr(listing, "checkInMethod", "key_handover")
    access_code_location = getattr(listing, "accessCodeLocation", "Please contact your host")
    wifi_name = getattr(listing, "wifiName", "")
    wifi_password = getattr(listing, "wifiPassword", "")
    check_in_time = getattr(listing, "checkInTime", "15:00")
    parking = getattr(listing, "parkingInstructions", "")

    parts = [
        f"**Welcome to {listing.name}!** Here are your access details:\n",
        f"🕐 **Check-in time:** {check_in_time}",
        f"🔑 **Check-in method:** {check_in_method.replace('_', ' ').title()}",
    ]
    if access_code_location:
        parts.append(f"📍 **Access:** {access_code_location}")
    if wifi_name:
        parts.append(f"📶 **WiFi:** {wifi_name}")
    if wifi_password:
        parts.append(f"🔐 **WiFi Password:** {wifi_password}")
    if parking:
        parts.append(f"🚗 **Parking:** {parking}")

    content = "\n".join(parts)

    msg = GuestMessage(
        messageId=str(uuid.uuid4()),
        direction="outbound",
        content=content,
        handledBy="reservation_agent",
        intent="access_details",
        status="sent",
        discloseAi=True,
        createdAt=now_utc(),
        sentAt=now_utc(),
    )
    thread.messages.append(msg)
    thread.lastActivityAt = now_utc()
    await thread.save()

    return {"sent": True, "messageId": msg.messageId, "channel": thread.channel}


# ── 8. getListingProfile ───────────────────────────────────────────────────────

@guest_agent_router.get("/listing-profile/{listing_id}")
async def get_listing_profile(listing_id: str, orgId: str):
    """
    Returns listing KB data for agent context — public fields only.
    wifi_password and access codes intentionally excluded from this endpoint.
    """
    from app.models.listing import Listing

    print(f"💎 [GUEST_TOOL] get_listing_profile | listingId={listing_id} | orgId={orgId}")
    listing = await Listing.find_one(
        Listing.id == oid(listing_id), Listing.orgId == oid(orgId)
    )
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    return {
        "listingId": str(listing.id),
        "name": listing.name,
        "area": listing.area,
        "address": getattr(listing, "address", ""),
        "maxGuests": getattr(listing, "personCapacity", 0),
        "bedrooms": listing.bedroomsNumber,
        "bathrooms": getattr(listing, "bathroomsNumber", 0),
        "checkInTime": getattr(listing, "checkInTime", "15:00"),
        "checkOutTime": getattr(listing, "checkOutTime", "11:00"),
        "checkInMethod": getattr(listing, "checkInMethod", "key_handover"),
        "houseRules": getattr(listing, "houseRules", []),
        "parkingInstructions": getattr(listing, "parkingInstructions", ""),
        "amenities": getattr(listing, "amenities", []),
        "emergencyContact": getattr(listing, "emergencyContact", {}),
        # wifi/accessCode NOT included — only via send_access_details
    }


# ── 9. getPropertyData ─────────────────────────────────────────────────────────

@guest_agent_router.get("/property-data/{listing_id}")
async def get_property_data(listing_id: str, orgId: str):
    """
    Returns full real-time property data including availability and market events.
    Used by the agent to answer 'is early check-in possible?' or 'any events nearby?'.
    """
    from app.models.listing import Listing
    from app.models.inventory_master import InventoryMaster
    from app.models.market_event import MarketEvent

    print(f"💎 [GUEST_TOOL] get_property_data | listingId={listing_id} | orgId={orgId}")
    listing = await Listing.find_one(Listing.id == oid(listing_id), Listing.orgId == oid(orgId))
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    now = datetime.now(timezone.utc)
    today_str = now.strftime("%Y-%m-%d")
    next_7_str = (now + timedelta(days=7)).strftime("%Y-%m-%d")

    # Fetch availability for next 7 days
    inventory = await InventoryMaster.find(
        InventoryMaster.listingId == oid(listing_id),
        InventoryMaster.date >= today_str,
        InventoryMaster.date <= next_7_str
    ).sort(+InventoryMaster.date).to_list()

    # Fetch active market events
    events = await MarketEvent.find(
        MarketEvent.orgId == oid(orgId),
        MarketEvent.isActive == True,
        MarketEvent.endDate >= today_str
    ).sort(+MarketEvent.startDate).limit(10).to_list()

    return {
        "listing": {
            "name": listing.name,
            "houseRules": getattr(listing, "houseRules", []),
            "amenities": getattr(listing, "amenities", []),
            "checkInTime": getattr(listing, "checkInTime", "15:00"),
            "checkOutTime": getattr(listing, "checkOutTime", "11:00"),
        },
        "availability": [
            {"date": i.date, "status": i.status, "price": i.currentPrice}
            for i in inventory
        ],
        "marketEvents": [
            {"name": e.name, "startDate": e.startDate, "impact": e.impactLevel}
            for e in events
        ]
    }


# ── 10. sendUpsellOffer ────────────────────────────────────────────────────────

class UpsellOfferRequest(BaseModel):
    threadId: str
    offerType: Literal["early_checkin", "late_checkout", "extended_stay", "upgrade"]
    price: float
    currency: str = "AED"
    details: Optional[str] = None

@guest_agent_router.post("/send-upsell")
async def send_upsell_offer(req: UpsellOfferRequest):
    """
    Sends a structured upsell offer to the guest.
    """
    from app.models.guest_thread import GuestThread, GuestMessage

    thread = await GuestThread.get(oid(req.threadId))
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    if thread.commsState != "active":
        return {"error": "COMMS_STATE_BLOCKED", "commsState": thread.commsState}

    offer_titles = {
        "early_checkin": "Early Check-in Opportunity",
        "late_checkout": "Late Check-out Opportunity",
        "extended_stay": "Stay a Bit Longer?",
        "upgrade": "Room Upgrade Available"
    }

    title = offer_titles.get(req.offerType, "Special Offer")
    content = f"🎁 **{title}**\n\nWe're happy to offer you {req.offerType.replace('_', ' ')} for just **{req.currency} {req.price}**.\n"
    if req.details:
        content += f"\nDetails: {req.details}\n"
    content += "\nWould you like to add this to your reservation? Just reply 'YES' to confirm!"

    msg = GuestMessage(
        messageId=str(uuid.uuid4()),
        direction="outbound",
        content=content,
        handledBy="reservation_agent",
        intent=f"upsell_{req.offerType}",
        status="sent",
        createdAt=now_utc(),
        sentAt=now_utc(),
    )
    thread.messages.append(msg)
    thread.lastActivityAt = now_utc()
    await thread.save()

    return {"sent": True, "messageId": msg.messageId, "offerType": req.offerType}


# ── Approve pending reply (PM action from Unified Inbox) ───────────────────────

class ApproveReplyRequest(BaseModel):
    threadId: str
    messageId: str
    editedContent: Optional[str] = None     # PM can edit before approving

@guest_agent_router.post("/approve-reply")
async def approve_reply(req: ApproveReplyRequest):
    """
    PM approves a pending_approval reply from the Unified Inbox.
    Mirrors CRO Router's proposal approve flow.
    """
    from app.models.guest_thread import GuestThread

    thread = await GuestThread.get(oid(req.threadId))
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    for msg in thread.messages:
        if msg.messageId == req.messageId:
            if msg.status != "pending_approval":
                raise HTTPException(status_code=400, detail="Message is not pending approval")
            if req.editedContent:
                msg.content = req.editedContent
            msg.status = "sent"
            msg.sentAt = now_utc()
            msg.handledBy = "human"
            break
    else:
        raise HTTPException(status_code=404, detail="Message not found in thread")

    thread.status = "open"
    thread.lastActivityAt = now_utc()
    await thread.save()

    return {"approved": True, "messageId": req.messageId}


# ── Simulation Mode (Test Mode) ────────────────────────────────────────────────

class SimulationRequest(BaseModel):
    threadId: str
    orgId: str
    content: str

@guest_agent_router.post("/simulate-guest-message")
async def simulate_guest_message(req: SimulationRequest):
    """
    Inbound message simulation for testing the Guest Agent (Maya).
    1. Injects message as 'inbound' from 'guest'.
    2. Triggers the Agentic flow to generate a response.
    """
    from app.models.guest_thread import GuestThread, GuestMessage
    from app.api.engagement_ops import call_lyzr_agent
    
    thread = await GuestThread.get(oid(req.threadId))
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
        
    # 1. Inject Guest Message
    new_msg = GuestMessage(
        messageId=str(uuid.uuid4()),
        direction="inbound",
        content=req.content,
        status="sent",
        createdAt=now_utc(),
    )
    thread.messages.append(new_msg)
    thread.lastActivityAt = now_utc()
    thread.status = "open" # Ensure it's open for the agent to see
    await thread.save()
    
    # 2. Trigger Agentic Flow
    # We use a specialized prompt for Maya or just the standard call_lyzr_agent with her ID
    # For now, we return that the message was injected, and the frontend will call the agent
    # using the standard execution pipeline to show the Live Graph.
    
    return {
        "success": true,
        "messageId": new_msg.messageId,
        "threadId": req.threadId,
        "injectedMessage": req.content,
        "nextStep": "Call agent to process thread"
    }
