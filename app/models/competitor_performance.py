"""
CompetitorPerformance — Collection 2 of 3 (Airbtics raw data)

Stores monthly performance for each Airbtics competitor listing.
Source: part-00294-56eb3db9*.csv (3,482 rows — past)
        part-00294-cac8f0ac*.csv (3,336 rows — future)
One document per listing per month. No aggregation.

Used by the /nearby-comps endpoint to fetch performance data for
competitor listings identified by the proximity search.
"""
from datetime import datetime, timezone
from typing import Optional
from beanie import Document
from pydantic import Field


def now_utc():
    return datetime.now(timezone.utc)


class CompetitorPerformance(Document):
    marketId: str                          # e.g. "2286"
    airbticsListingId: str                 # joins to CompetitorListing.airbticsListingId
    date: str                              # "YYYY-MM-01" — first of the month
    dataType: str = "historical"           # "historical" or "forecast"

    # Raw performance — stored exactly as CSV, no aggregation
    vacantDays: int = 0
    reservedDays: int = 0
    occupancy: float = 0.0                 # 0.0 to 1.0
    revenue: float = 0.0                   # USD
    rateAvg: float = 0.0                   # USD avg nightly rate
    bookedRateAvg: float = 0.0             # USD booked rate avg
    bookingLeadTimeAvg: Optional[float] = None
    lengthOfStayAvg: Optional[float] = None
    minNightsAvg: Optional[float] = None
    nativeBookedRateAvg: float = 0.0       # AED booked rate avg
    nativeRateAvg: float = 0.0             # AED avg nightly rate
    nativeRevenue: float = 0.0             # AED revenue

    createdAt: datetime = Field(default_factory=now_utc)

    class Settings:
        name = "competitor_performances"
        indexes = [
            [("marketId", 1), ("airbticsListingId", 1), ("date", 1)],
            [("marketId", 1), ("date", 1)],
        ]
