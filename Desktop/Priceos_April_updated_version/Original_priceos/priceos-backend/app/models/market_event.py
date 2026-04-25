from datetime import datetime, timezone
from typing import Optional, Literal, List
from beanie import Document
from pydantic import Field
from beanie import PydanticObjectId as ObjectId

def now_utc():
    return datetime.now(timezone.utc)

class MarketEvent(Document):
    orgId: ObjectId
    listingId: Optional[ObjectId] = None  # None indicates portfolio-wide
    name: str
    startDate: str  # "YYYY-MM-DD"
    endDate: str    # "YYYY-MM-DD"
    area: Optional[str] = None
    areas: List[str] = Field(default_factory=list)
    impactLevel: Literal["high", "medium", "low"] = "medium"
    upliftPct: float = 0.0
    description: Optional[str] = None
    source: str = "ai_detected"
    isActive: bool = True
    createdAt: datetime = Field(default_factory=now_utc)
    updatedAt: datetime = Field(default_factory=now_utc)

    class Settings:
        name = "market_events"
        indexes = [
            [("orgId", 1), ("startDate", 1), ("endDate", 1)]
        ]
