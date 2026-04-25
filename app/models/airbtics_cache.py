from datetime import datetime, timezone
from typing import Dict, Any
from beanie import Document
from pydantic import Field

def now_utc():
    return datetime.now(timezone.utc)

class AirbticsCache(Document):
    cacheKey: str
    data: Dict[str, Any]
    expiresAt: datetime
    createdAt: datetime = Field(default_factory=now_utc)
    updatedAt: datetime = Field(default_factory=now_utc)

    class Settings:
        name = "airbtics_caches"
        indexes = [
            [("cacheKey", 1)],
            [("expiresAt", 1)]
        ]
