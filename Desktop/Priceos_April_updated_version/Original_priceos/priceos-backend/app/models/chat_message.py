from typing import Optional, Dict, Any, Literal
from datetime import datetime
from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field

class ChatContext(BaseModel):
    type: Literal["portfolio", "property"]
    propertyId: Optional[PydanticObjectId] = None

class ChatMessage(Document):
    orgId: PydanticObjectId
    sessionId: str
    role: Literal["user", "assistant", "system"]
    content: str
    context: Optional[ChatContext] = None
    metadata: Optional[Dict[str, Any]] = None
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    updatedAt: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "chatmessages"
        indexes = [
            "orgId",
            "sessionId"
        ]
