"""
models/guest_thread.py
Conversation thread between a guest and the system, with embedded messages.
comms_state is the critical gate controlling all agent sends.
"""
from datetime import datetime, timezone
from typing import Optional, Literal, List
from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field


def now_utc():
    return datetime.now(timezone.utc)


class GuestMessage(BaseModel):
    messageId: str
    direction: Literal["inbound", "outbound"]
    content: str
    handledBy: Literal["reservation_agent", "human", "system"] = "reservation_agent"
    intent: Optional[str] = None
    sentiment: Optional[str] = None
    confidence: Optional[float] = None
    discloseAi: bool = True
    status: Literal["draft", "pending_approval", "sent", "failed"] = "draft"
    createdAt: datetime = Field(default_factory=now_utc)
    sentAt: Optional[datetime] = None


class GuestThread(Document):
    # Linkage
    orgId: PydanticObjectId
    reservationId: str
    guestId: Optional[str] = None
    listingId: Optional[PydanticObjectId] = None

    # Channel — V1: email only; V2 adds whatsapp, sms, voice
    channel: Literal["email", "internal"] = "email"

    # ── CRITICAL GATE ─────────────────────────────────────────────────────────
    # active   → agent may send (if confidence >= threshold)
    # paused   → classify + draft only, NEVER send (human takeover)
    # syncing  → queue messages, wait for sync to complete
    # disabled → agent takes NO action at all
    commsState: Literal["active", "paused", "syncing", "disabled"] = "active"

    status: Literal["open", "urgent", "pending_approval", "closed"] = "open"
    assignedTo: Optional[str] = None

    # Embedded messages (denormalised for fast reads)
    messages: List[GuestMessage] = Field(default_factory=list)

    # Linked ops tickets
    linkedTicketIds: List[str] = Field(default_factory=list)

    # Audit
    openedAt: datetime = Field(default_factory=now_utc)
    lastActivityAt: datetime = Field(default_factory=now_utc)
    closedAt: Optional[datetime] = None
    closureReason: Optional[str] = None

    class Settings:
        name = "guest_threads"
        indexes = [
            [("orgId", 1), ("status", 1), ("lastActivityAt", -1)],
            [("reservationId", 1)],
            [("listingId", 1), ("status", 1)],
            [("commsState", 1)],
        ]
