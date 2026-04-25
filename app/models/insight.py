from datetime import datetime, timezone
from typing import Optional, Literal, Dict, Any
from beanie import Document
from pydantic import BaseModel, Field
from beanie import PydanticObjectId as ObjectId

def now_utc():
    return datetime.now(timezone.utc)

InsightCategory = Literal[
    "BOOKING_PACE", "LEAD_TIME", "CANCELLATION_RISK", "OCCUPANCY",
    "GAP_FILL", "LOS_OPTIMIZATION", "COMPETITOR_RATE", "DAY_OF_WEEK",
    "REVIEW_SCORE", "EVENT_IMPACT", "SEASONAL_SHIFT", "CHANNEL_MIX"
]

InsightStatus = Literal["pending", "approved", "modified", "rejected", "snoozed", "superseded"]

class InsightAction(BaseModel):
    type: Literal["price_increase", "price_decrease", "gap_fill", "min_stay_change", "block", "advisory"]
    adjustPct: Optional[float] = None
    absolutePrice: Optional[float] = None
    dateRange: Optional[Dict[str, str]] = None
    scope: Optional[str] = None
    data: Optional[Dict[str, Any]] = None

class Insight(Document):
    orgId: ObjectId
    listingId: Optional[ObjectId] = None
    category: InsightCategory
    severity: Literal["high", "medium", "low"] = "medium"
    status: InsightStatus = "pending"
    title: str
    summary: Optional[str] = None
    confidence: float = 0.7
    action: Optional[InsightAction] = None
    modifiedAction: Optional[InsightAction] = None
    resolvedBy: Optional[str] = None
    resolvedAt: Optional[datetime] = None
    snoozeUntil: Optional[datetime] = None
    pushedAt: Optional[datetime] = None
    detectorKey: Optional[str] = None
    signalData: Optional[Dict[str, Any]] = None
    createdAt: datetime = Field(default_factory=now_utc)
    updatedAt: datetime = Field(default_factory=now_utc)

    class Settings:
        name = "insights"
        indexes = [
            [("orgId", 1), ("status", 1), ("createdAt", -1)]
        ]
