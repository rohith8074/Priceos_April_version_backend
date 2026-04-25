"""
models/ops_ticket.py
Operational tickets raised by the Guest Reply Agent when a guest reports a
physical issue (broken AC, noise, access problem, etc.)
"""
from datetime import datetime, timezone
from typing import Optional, Literal
from beanie import Document, PydanticObjectId
from pydantic import Field


def now_utc():
    return datetime.now(timezone.utc)


class OpsTicket(Document):
    # Linkage
    orgId: PydanticObjectId
    reservationId: Optional[str] = None
    listingId: Optional[PydanticObjectId] = None
    threadId: Optional[str] = None          # guest_thread origin

    # Ticket details
    category: Literal[
        "maintenance", "housekeeping", "access", "noise", "amenity_fault", "other"
    ] = "other"
    description: str
    severity: Literal["critical", "high", "medium", "low"] = "medium"
    slaHours: int = 24                       # critical=2, high=4, medium=24, low=72

    # Lifecycle
    status: Literal["open", "assigned", "in_progress", "resolved", "closed"] = "open"
    createdBy: Literal["reservation_agent", "human"] = "reservation_agent"
    assignedTo: Optional[str] = None        # staff member or team

    # Audit
    createdAt: datetime = Field(default_factory=now_utc)
    updatedAt: datetime = Field(default_factory=now_utc)
    resolvedAt: Optional[datetime] = None

    class Settings:
        name = "ops_tickets"
        indexes = [
            [("orgId", 1), ("status", 1)],
            [("listingId", 1), ("status", 1)],
            [("reservationId", 1)],
            [("createdAt", -1)],
        ]
