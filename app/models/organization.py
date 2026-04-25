from datetime import datetime, timezone
from typing import List, Optional, Any, Dict, Literal
from beanie import Document
from pydantic import BaseModel, EmailStr, Field

SystemState = Literal["connected", "observing", "simulating", "active", "paused"]

class GuardrailsSettings(BaseModel):
    maxSingleDayChangePct: float = 15.0
    autoApproveThreshold: float = 5.0
    absoluteFloorMultiplier: float = 0.5
    absoluteCeilingMultiplier: float = 3.0

class AutomationSettings(BaseModel):
    autoPushApproved: bool = False
    dailyPipelineRun: bool = True

class OverridesSettings(BaseModel):
    currency: Optional[str] = None
    timezone: Optional[str] = None
    weekendDefinition: Optional[str] = None

class OrganizationSettings(BaseModel):
    guardrails: GuardrailsSettings = Field(default_factory=GuardrailsSettings)
    automation: AutomationSettings = Field(default_factory=AutomationSettings)
    overrides: OverridesSettings = Field(default_factory=OverridesSettings)

class OnboardingTracker(BaseModel):
    step: Literal["connect", "select", "market", "strategy", "complete"] = "connect"
    selectedListingIds: List[str] = Field(default_factory=list)
    activatedListingIds: List[str] = Field(default_factory=list)
    completedAt: Optional[datetime] = None
    listings: Optional[List[Dict[str, Any]]] = None

def now_utc():
    return datetime.now(timezone.utc)

class Organization(Document):
    name: str
    email: EmailStr
    passwordHash: str
    refreshToken: Optional[str] = None
    role: Literal["owner", "admin", "viewer"] = "owner"
    isApproved: bool = False
    fullName: Optional[str] = None
    hostawayApiKey: Optional[str] = None
    hostawayAccountId: Optional[str] = None
    marketCode: str = "UAE_DXB"
    currency: str = "AED"
    timezone: str = "Asia/Dubai"
    plan: Literal["starter", "growth", "scale"] = "starter"
    systemState: SystemState = "connected"
    systemStateSince: Optional[datetime] = None
    pauseReason: Optional[str] = None
    onboarding: OnboardingTracker = Field(default_factory=OnboardingTracker)
    settings: OrganizationSettings = Field(default_factory=OrganizationSettings)
    createdAt: datetime = Field(default_factory=now_utc)
    updatedAt: datetime = Field(default_factory=now_utc)

    class Settings:
        name = "organizations"
