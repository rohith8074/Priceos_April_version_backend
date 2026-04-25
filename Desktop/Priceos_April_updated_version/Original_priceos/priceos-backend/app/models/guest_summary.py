from typing import List, Literal
from datetime import datetime
from beanie import Document, PydanticObjectId
from pydantic import Field

class GuestSummary(Document):
    orgId: PydanticObjectId
    listingId: PydanticObjectId
    dateFrom: str
    dateTo: str
    sentiment: Literal["Positive", "Neutral", "Needs Attention"] = "Neutral"
    themes: List[str] = []
    actionItems: List[str] = []
    bulletPoints: List[str] = []
    totalConversations: int = 0
    needsReplyCount: int = 0
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    updatedAt: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "guestsummaries"
        indexes = [
            "orgId",
            "listingId"
        ]
