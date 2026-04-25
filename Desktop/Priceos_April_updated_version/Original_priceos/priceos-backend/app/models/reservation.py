from datetime import datetime, timezone
from typing import Optional, Literal
from beanie import Document
from pydantic import Field
from beanie import PydanticObjectId as ObjectId

def now_utc():
    return datetime.now(timezone.utc)

class Reservation(Document):
    orgId: ObjectId
    listingId: ObjectId
    hostawayReservationId: Optional[str] = None
    guestName: str = "Unknown Guest"
    guestEmail: Optional[str] = None
    guestPhone: Optional[str] = None
    checkIn: str  # "YYYY-MM-DD"
    checkOut: str  # "YYYY-MM-DD"
    nights: int = 1
    guests: int = 1
    totalPrice: float = 0.0
    channelName: str = "Direct"
    status: Literal["confirmed", "pending", "cancelled", "checked_in", "checked_out", "inquiry"] = "confirmed"
    source: Optional[str] = None
    notes: Optional[str] = None
    createdAt: datetime = Field(default_factory=now_utc)
    updatedAt: datetime = Field(default_factory=now_utc)

    class Settings:
        name = "reservations"
        indexes = [
            [("listingId", 1), ("checkIn", 1), ("checkOut", 1)]
        ]
