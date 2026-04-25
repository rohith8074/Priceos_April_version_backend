"""
CompetitorReview — Collection 3 of 3 (Airbtics raw data)

Stores monthly review counts for each Airbtics competitor listing.
Source: part-00294-bc49a9e7*.csv (1,085 rows)
One document per listing per month. No aggregation.

Used for sentiment/popularity signals in market research.
"""
from datetime import datetime, timezone
from typing import List, Optional
from beanie import Document
from pydantic import Field


def now_utc():
    return datetime.now(timezone.utc)


class CompetitorReview(Document):
    marketId: str                          # e.g. "2286"
    airbticsListingId: str                 # joins to CompetitorListing.airbticsListingId
    date: str                              # "YYYY-MM-01"
    numReviews: int = 0
    reviewerIds: List[str] = Field(default_factory=list)

    createdAt: datetime = Field(default_factory=now_utc)

    class Settings:
        name = "competitor_reviews"
        indexes = [
            [("marketId", 1), ("airbticsListingId", 1), ("date", 1)],
        ]
