"""
models/comms_policy.py
Per-property/org communication policy for the Guest Reply Agent.
"""
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field


def now_utc():
    return datetime.now(timezone.utc)


class EscalationContact(BaseModel):
    name: str
    phone: str
    email: Optional[str] = None


class CommsPolicy(Document):
    orgId: PydanticObjectId
    listingId: Optional[PydanticObjectId] = None   # None = org-wide default

    # Tone & language
    tone: str = "professional"                      # formal | friendly | professional
    languages: List[str] = Field(default_factory=lambda: ["en"])

    # AI disclosure
    discloseAiDefault: bool = True
    discloseAiByChannel: Dict[str, bool] = Field(
        default_factory=lambda: {"email": True, "internal": False}
    )

    # Auto-send behaviour
    autoSendThreshold: float = 0.85
    requireApprovalSentimentThreshold: float = 0.75

    # Upsell
    upsellEnabled: bool = True
    upsellTimingHoursBeforeCheckin: int = 48

    # Escalation contacts
    escalationContacts: List[EscalationContact] = Field(default_factory=list)

    # Proactive sequence
    sendWelcomeOnConfirm: bool = True
    sendAccessDetailsHoursBeforeCheckin: int = 48
    sendReviewNudgeHoursAfterCheckout: int = 24

    createdAt: datetime = Field(default_factory=now_utc)
    updatedAt: datetime = Field(default_factory=now_utc)

    class Settings:
        name = "comms_policies"
        indexes = [
            [("orgId", 1), ("listingId", 1)],
        ]
