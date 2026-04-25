from datetime import datetime, timezone
from typing import Optional, Literal, List, Dict, Any
from beanie import Document
from pydantic import BaseModel, Field
from beanie import PydanticObjectId as ObjectId

def now_utc():
    return datetime.now(timezone.utc)

class Comp(BaseModel):
    name: str
    source: str
    sourceUrl: Optional[str] = None
    rating: Optional[float] = None
    reviews: Optional[int] = None
    avgRate: float
    weekdayRate: Optional[float] = None
    weekendRate: Optional[float] = None
    minRate: Optional[float] = None
    maxRate: Optional[float] = None

class BenchmarkData(Document):
    orgId: ObjectId
    listingId: ObjectId
    dateFrom: str
    dateTo: str
    p25Rate: Optional[float] = None
    p50Rate: Optional[float] = None
    p75Rate: Optional[float] = None
    p90Rate: Optional[float] = None
    avgWeekday: Optional[float] = None
    avgWeekend: Optional[float] = None
    yourPrice: Optional[float] = None
    percentile: Optional[float] = None
    verdict: Optional[Literal["UNDERPRICED", "FAIR", "SLIGHTLY_ABOVE", "OVERPRICED"]] = None
    rateTrend: Optional[Literal["rising", "stable", "falling"]] = None
    trendPct: Optional[float] = None
    recommendedWeekday: Optional[float] = None
    recommendedWeekend: Optional[float] = None
    recommendedEvent: Optional[float] = None
    reasoning: Optional[str] = None
    comps: List[Comp] = Field(default_factory=list)
    createdAt: datetime = Field(default_factory=now_utc)
    updatedAt: datetime = Field(default_factory=now_utc)

    class Settings:
        name = "benchmark_data"
        indexes = [
            [("listingId", 1), ("dateFrom", 1), ("dateTo", 1)]
        ]
