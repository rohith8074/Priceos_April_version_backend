from datetime import datetime, timezone
from typing import Optional, Literal, List
from beanie import Document
from pydantic import Field
from beanie import PydanticObjectId as ObjectId

def now_utc():
    return datetime.now(timezone.utc)

RuleType = Literal["SEASON", "EVENT", "ADMIN_BLOCK", "LOS_DISCOUNT"]
RuleCategory = Literal[
    "GUARDRAILS", "SEASONS", "LEAD_TIME", "GAP_LOGIC", "LOS_DISCOUNTS", "DATE_OVERRIDES", "OCCUPANCY"
]

class PricingRule(Document):
    orgId: ObjectId
    listingId: Optional[ObjectId] = None
    groupId: Optional[ObjectId] = None
    scope: Literal["listing", "group"] = "listing"
    ruleType: RuleType
    ruleCategory: Optional[RuleCategory] = None
    name: str
    enabled: bool = True
    priority: int = 0
    
    # Conditions
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    daysOfWeek: Optional[List[int]] = None
    minNights: Optional[int] = None
    
    # Actions
    priceOverride: Optional[float] = None
    priceAdjPct: Optional[float] = None
    minPriceOverride: Optional[float] = None
    maxPriceOverride: Optional[float] = None
    minStayOverride: Optional[int] = None
    
    isBlocked: bool = False
    closedToArrival: bool = False
    closedToDeparture: bool = False
    suspendLastMinute: bool = False
    suspendGapFill: bool = False
    
    createdAt: datetime = Field(default_factory=now_utc)
    updatedAt: datetime = Field(default_factory=now_utc)

    class Settings:
        name = "pricing_rules"
        indexes = [
            [("listingId", 1), ("enabled", 1)],
            [("groupId", 1), ("enabled", 1)]
        ]
