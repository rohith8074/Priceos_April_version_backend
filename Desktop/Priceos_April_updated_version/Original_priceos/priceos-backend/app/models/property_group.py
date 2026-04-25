from typing import Optional, List
from datetime import datetime
from beanie import Document, PydanticObjectId
from pydantic import Field

class PropertyGroup(Document):
    orgId: PydanticObjectId
    name: str
    description: Optional[str] = None
    color: str = "#6366f1"
    listingIds: List[PydanticObjectId] = []
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    updatedAt: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "propertygroups"
        indexes = [
            "orgId"
        ]
