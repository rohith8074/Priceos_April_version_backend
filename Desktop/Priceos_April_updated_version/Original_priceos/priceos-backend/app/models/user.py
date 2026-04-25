from datetime import datetime, timezone
from typing import Optional, Literal
from beanie import Document, PydanticObjectId
from pydantic import EmailStr, Field

def now_utc():
    return datetime.now(timezone.utc)

class User(Document):
    name: str
    email: EmailStr
    passwordHash: str
    refreshToken: Optional[str] = None
    orgId: Optional[PydanticObjectId] = None
    role: Literal["owner", "admin", "viewer"] = "owner"
    isApproved: bool = True
    fullName: Optional[str] = None
    plan: Literal["starter", "growth", "scale"] = "starter"
    onboardingStep: Optional[str] = "complete"
    createdAt: datetime = Field(default_factory=now_utc)
    updatedAt: datetime = Field(default_factory=now_utc)

    class Settings:
        name = "users"
