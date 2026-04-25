from typing import Optional, Literal, List
from datetime import datetime
from beanie import Document, PydanticObjectId
from pydantic import Field

class SourceRun(Document):
    orgId: PydanticObjectId
    sourceId: str
    status: Literal["running", "success", "error"] = "running"
    startedAt: datetime = Field(default_factory=datetime.utcnow)
    completedAt: Optional[datetime] = None
    durationMs: Optional[int] = None
    recordsProcessed: Optional[int] = None
    signalsGenerated: Optional[int] = None
    error: Optional[str] = None
    logs: List[str] = []
    triggeredBy: Literal["manual", "schedule", "system"] = "manual"
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    updatedAt: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "sourceruns"
        indexes = [
            "orgId",
            "sourceId",
            "-startedAt"
        ]
