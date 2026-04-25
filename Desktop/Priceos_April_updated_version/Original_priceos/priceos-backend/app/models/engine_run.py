from datetime import datetime, timezone
from typing import Optional, Literal
from beanie import Document
from pydantic import Field
from beanie import PydanticObjectId as ObjectId

def now_utc():
    return datetime.now(timezone.utc)

class EngineRun(Document):
    orgId: ObjectId
    listingId: ObjectId
    startedAt: datetime = Field(default_factory=now_utc)
    status: Literal["SUCCESS", "FAILED", "RUNNING"] = "RUNNING"
    errorMessage: Optional[str] = None
    daysChanged: Optional[int] = None
    durationMs: Optional[int] = None
    batchId: Optional[str] = None
    createdAt: datetime = Field(default_factory=now_utc)
    updatedAt: datetime = Field(default_factory=now_utc)

    class Settings:
        name = "engine_runs"
        indexes = [
            [("orgId", 1)]
        ]
