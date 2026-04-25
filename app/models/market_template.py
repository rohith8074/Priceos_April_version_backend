from typing import List, Optional, Literal
from datetime import datetime
from beanie import Document
from pydantic import BaseModel, Field

class SeasonalPattern(BaseModel):
    month: int
    demandScore: float
    ratePremiumPct: float
    notes: Optional[str] = None

class GuardrailDefaults(BaseModel):
    maxSingleDayChangePct: float = 15.0
    autoApproveThreshold: float = 5.0
    absoluteFloorMultiplier: float = 0.5
    absoluteCeilingMultiplier: float = 3.0

class EventApiConfig(BaseModel):
    ticketmasterCity: Optional[str] = None
    eventbriteCity: Optional[str] = None
    customKeywords: List[str] = []

class RegulatoryFlags(BaseModel):
    hasNightCap: bool = False
    nightCapPerYear: Optional[int] = None
    requiresLicence: bool = False
    licenceFieldLabel: Optional[str] = None

class MarketTemplate(Document):
    marketCode: str
    displayName: str
    country: str
    currency: str
    timezone: str
    weekendDefinition: Literal["thu_fri", "fri_sat", "sat_sun"]
    flag: str
    guardrailDefaults: GuardrailDefaults = Field(default_factory=GuardrailDefaults)
    seasonalPatterns: List[SeasonalPattern] = []
    eventApiConfig: EventApiConfig = Field(default_factory=EventApiConfig)
    regulatoryFlags: Optional[RegulatoryFlags] = None
    isActive: bool = True
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    updatedAt: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "markettemplates"
        indexes = [
            "marketCode"
        ]
