from typing import List, Optional
from datetime import datetime
from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field

class HostawayMessage(BaseModel):
    sender: str
    text: str
    timestamp: str

class HostawayConversation(Document):
    orgId: PydanticObjectId
    listingId: PydanticObjectId
    hostawayConversationId: str
    guestName: str = "Unknown Guest"
    guestEmail: Optional[str] = None
    reservationId: Optional[str] = None
    messages: List[HostawayMessage] = []
    dateFrom: str
    dateTo: str
    needsReply: bool = False
    syncedAt: datetime = Field(default_factory=datetime.utcnow)
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    updatedAt: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "hostawayconversations"
        indexes = [
            "listingId",
            "hostawayConversationId"
        ]
