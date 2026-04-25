"""
CompetitorListing — Collection 1 of 3 (Airbtics raw data)

Stores static details for each Airbtics competitor listing.
Source: part-00294-e685bf03*.csv (302 rows)
One document per competitor property.

Used by the /nearby-comps endpoint to find competitors within a radius
using lat/lon + bedrooms.
"""
from datetime import datetime, timezone
from typing import Optional, List
from beanie import Document
from pydantic import Field


def now_utc():
    return datetime.now(timezone.utc)


class CompetitorListing(Document):
    marketId: str                          # e.g. "2286" (Dubai)
    airbticsListingId: str                 # Airbtics listing_id (NOT Hostaway ID)
    listingName: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    bedrooms: int = 1
    beds: Optional[int] = None
    baths: Optional[float] = None
    guests: Optional[int] = None
    hostName: str = ""
    roomType: str = ""                     # entire_home, private_room, etc.
    amenities: List[str] = Field(default_factory=list)
    ratingOverall: Optional[float] = None
    numReviews: int = 0
    currency: str = "AED"

    # TTM (trailing twelve months) snapshot — for broad context
    ttmOccupancy: Optional[float] = None
    ttmAvgRateNative: Optional[float] = None
    ttmRevenueNative: Optional[float] = None

    # L90D (last 90 days) snapshot
    l90dOccupancy: Optional[float] = None
    l90dAvgRateNative: Optional[float] = None

    createdAt: datetime = Field(default_factory=now_utc)

    class Settings:
        name = "competitor_listings"
        indexes = [
            [("marketId", 1), ("airbticsListingId", 1)],
            [("marketId", 1), ("bedrooms", 1)],
            [("latitude", 1), ("longitude", 1)],
        ]
