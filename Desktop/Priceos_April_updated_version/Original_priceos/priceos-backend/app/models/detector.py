from typing import Optional, Dict, Any
from datetime import datetime
from beanie import Document
from pydantic import Field

class Detector(Document):
    detectorId: str
    name: str
    category: str
    triggerSource: str
    description: Optional[str] = None
    isEnabled: bool = True
    lastTriggeredAt: Optional[datetime] = None
    lastSignalsFound: int = 0
    config: Dict[str, Any] = Field(default_factory=dict)
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    updatedAt: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "detectors"
        indexes = [
            [("detectorId", 1)],   # unique index already exists in DB
        ]
