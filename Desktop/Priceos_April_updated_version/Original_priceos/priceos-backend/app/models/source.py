from typing import Optional, Literal, Dict, Any
from datetime import datetime
from beanie import Document
from pydantic import Field

class Source(Document):
    sourceId: str
    name: str
    description: Optional[str] = None
    iconName: str = "Database"
    schedule: str = "0 */4 * * *"
    scheduleLabel: str = "Every 4 hours"
    isEnabled: bool = True
    lastRunAt: Optional[datetime] = None
    lastRunStatus: Literal["success", "error", "running", "idle"] = "idle"
    lastRunDurationMs: Optional[int] = None
    lastRunMetric: Optional[str] = None
    nextRunAt: Optional[datetime] = None
    config: Dict[str, Any] = Field(default_factory=dict)
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    updatedAt: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "sources"
        indexes = [
            "sourceId"
        ]
