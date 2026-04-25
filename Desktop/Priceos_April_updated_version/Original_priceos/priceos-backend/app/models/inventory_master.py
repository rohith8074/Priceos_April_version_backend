from datetime import datetime, timezone
from typing import Optional, Literal, Any
from beanie import Document
from pydantic import Field
from beanie import PydanticObjectId as ObjectId

def now_utc():
    return datetime.now(timezone.utc)

class InventoryMaster(Document):
    orgId: ObjectId
    listingId: ObjectId
    date: str  # "YYYY-MM-DD"
    currentPrice: float
    basePrice: Optional[float] = None
    status: Literal["available", "booked", "blocked", "pending"] = "available"
    minStay: Optional[int] = None
    maxStay: Optional[int] = None
    closedToArrival: bool = False
    closedToDeparture: bool = False
    
    # Staged change (HITL)
    proposedPrice: Optional[float] = None
    proposalStatus: Optional[Literal["pending", "approved", "rejected", "pushed", "rolled_back"]] = None
    changePct: Optional[float] = None
    reasoning: Optional[Any] = None
    batchId: Optional[str] = None
    
    # Rollback support
    previousPrice: Optional[float] = None
    pushedAt: Optional[datetime] = None
    
    # Sync
    hostawayStatus: Optional[str] = None
    lastSyncedAt: Optional[datetime] = None
    createdAt: datetime = Field(default_factory=now_utc)
    updatedAt: datetime = Field(default_factory=now_utc)

    class Settings:
        name = "inventory_masters"
        indexes = [
            [("listingId", 1), ("date", 1)],
            [("orgId", 1), ("proposalStatus", 1)]
        ]
