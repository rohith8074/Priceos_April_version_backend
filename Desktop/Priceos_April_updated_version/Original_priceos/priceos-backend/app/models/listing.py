from datetime import datetime, timezone
from typing import List, Optional, Literal
from beanie import Document
from pydantic import BaseModel, Field
from beanie import PydanticObjectId as ObjectId

def now_utc():
    return datetime.now(timezone.utc)

class OccupancyWindowProfile(BaseModel):
    startDay: int
    endDay: int
    highThresholdPct: float
    highAdjPct: float
    lowThresholdPct: float
    lowAdjPct: float

class GroupOccupancyProfile(BaseModel):
    startDay: int
    endDay: int
    occupancyPct: float
    sampleSize: int
    groupIds: List[str] = Field(default_factory=list)

class Listing(Document):
    orgId: ObjectId
    hostawayId: Optional[str] = None
    name: str
    city: str = ""
    countryCode: str = ""
    area: str = ""
    bedroomsNumber: int = 1
    bathroomsNumber: int = 1
    propertyTypeId: int = 0
    price: float
    currencyCode: str = "AED"
    personCapacity: Optional[int] = None
    amenities: List[str] = Field(default_factory=list)
    address: Optional[str] = None
    priceFloor: float = 0
    floorReasoning: Optional[str] = None
    priceCeiling: float = 0
    ceilingReasoning: Optional[str] = None
    guardrailsSource: Literal["manual", "ai", "market_template"] = "manual"
    
    # Last Minute
    lastMinuteEnabled: bool = False
    lastMinuteDaysOut: int = 7
    lastMinuteDiscountPct: float = 15
    lastMinuteMinStay: Optional[int] = None
    
    # Far Out
    farOutEnabled: bool = False
    farOutDaysOut: int = 90
    farOutMarkupPct: float = 10
    farOutMinStay: Optional[int] = None
    farOutMinPrice: float = 0
    
    # DOW pricing
    dowPricingEnabled: bool = False
    dowDays: List[int] = Field(default_factory=lambda: [4, 5])
    dowPriceAdjPct: float = 20
    dowMinStay: Optional[int] = None
    
    # Gap prevention
    gapPreventionEnabled: bool = True
    minFragmentThreshold: int = 3
    
    # Gap fill
    gapFillEnabled: bool = False
    gapFillLengthMin: int = 1
    gapFillLengthMax: int = 3
    gapFillDiscountPct: float = 10
    gapFillDiscountWeekdayPct: float = 0
    gapFillDiscountWeekendPct: float = 0
    gapFillMaxDaysUntilCheckin: int = 30
    gapFillOverrideCico: bool = True
    adjacentAdjustmentEnabled: bool = False
    adjacentAdjustmentPct: float = 0
    adjacentTurnoverCost: float = 0
    
    # Check-in/out restrictions
    allowedCheckinDays: List[int] = Field(default_factory=lambda: [1, 1, 1, 1, 1, 1, 1])
    allowedCheckoutDays: List[int] = Field(default_factory=lambda: [1, 1, 1, 1, 1, 1, 1])
    lowestMinStayAllowed: int = 1
    defaultMaxStay: int = 365
    
    # Occupancy-based adjustments
    occupancyEnabled: bool = False
    occupancyTargetPct: float = 75
    occupancyHighThresholdPct: float = 85
    occupancyHighAdjPct: float = 15
    occupancyLowThresholdPct: float = 50
    occupancyLowAdjPct: float = -10
    occupancyLookbackDays: int = 30
    occupancyWindowProfiles: List[OccupancyWindowProfile] = Field(default_factory=list)
    useGroupOccupancyProfile: bool = True
    groupOccupancyWeightPct: float = 50
    groupOccupancyProfiles: List[GroupOccupancyProfile] = Field(default_factory=list)
    basePriceSource: Literal["history_1y", "benchmark", "hostaway"] = "hostaway"
    basePriceConfidencePct: float = 0
    basePriceSampleSize: int = 0
    basePriceLastComputedAt: Optional[datetime] = None
    
    # Weekend minimum pricing
    weekendMinPrice: float = 0
    weekendDays: List[int] = Field(default_factory=lambda: [4, 5])
    
    # Gradual last-minute discount curve
    lastMinuteRampEnabled: bool = False
    lastMinuteRampDays: int = 15
    lastMinuteMaxDiscountPct: float = 30
    lastMinuteMinDiscountPct: float = 5
    isActive: bool = True
    createdAt: datetime = Field(default_factory=now_utc)
    updatedAt: datetime = Field(default_factory=now_utc)

    class Settings:
        name = "listings"
