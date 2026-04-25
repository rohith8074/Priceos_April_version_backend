from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.organization import Organization
from app.models.market_template import MarketTemplate

user_settings_router = APIRouter(prefix="/user", tags=["user-settings"])
markets_router = APIRouter(prefix="/markets", tags=["markets"])


class GuardrailsPayload(BaseModel):
    maxSingleDayChangePct: Optional[float] = None
    autoApproveThreshold: Optional[float] = None
    absoluteFloorMultiplier: Optional[float] = None
    absoluteCeilingMultiplier: Optional[float] = None


class AutomationPayload(BaseModel):
    autoPushApproved: Optional[bool] = None
    dailyPipelineRun: Optional[bool] = None


class OverridesPayload(BaseModel):
    currency: Optional[str] = None
    timezone: Optional[str] = None
    weekendDefinition: Optional[str] = None


class SettingsPayload(BaseModel):
    guardrails: Optional[GuardrailsPayload] = None
    automation: Optional[AutomationPayload] = None
    overrides: Optional[OverridesPayload] = None


class UserSettingsUpdateRequest(BaseModel):
    orgId: str
    name: Optional[str] = None
    fullName: Optional[str] = None
    email: Optional[str] = None
    hostawayApiKey: Optional[str] = None
    hostawayAccountId: Optional[str] = None
    marketCode: Optional[str] = None
    currency: Optional[str] = None
    timezone: Optional[str] = None
    settings: Optional[SettingsPayload] = None


@user_settings_router.get("/settings")
async def get_user_settings(orgId: str):
    org = await Organization.get(ObjectId(orgId))
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return {
        "id": str(org.id),
        "name": org.name or "",
        "fullName": org.fullName or "",
        "email": org.email,
        "role": org.role,
        "isApproved": org.isApproved,
        "plan": org.plan or "starter",
        "marketCode": org.marketCode or "UAE_DXB",
        "currency": org.currency or "AED",
        "timezone": org.timezone or "Asia/Dubai",
        "hostawayApiKey": org.hostawayApiKey or "",
        "hostawayAccountId": org.hostawayAccountId or "",
        "systemState": org.systemState or "connected",
        "settings": org.settings.model_dump() if org.settings else {},
    }


@user_settings_router.post("/settings")
async def update_user_settings(req: UserSettingsUpdateRequest):
    org = await Organization.get(ObjectId(req.orgId))
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    for field in ["name", "fullName", "email", "hostawayApiKey", "hostawayAccountId", "marketCode", "currency", "timezone"]:
        val = getattr(req, field)
        if val is not None:
            setattr(org, field, val)

    if req.settings:
        if req.settings.guardrails:
            g = req.settings.guardrails
            if g.maxSingleDayChangePct is not None:
                org.settings.guardrails.maxSingleDayChangePct = g.maxSingleDayChangePct
            if g.autoApproveThreshold is not None:
                org.settings.guardrails.autoApproveThreshold = g.autoApproveThreshold
            if g.absoluteFloorMultiplier is not None:
                org.settings.guardrails.absoluteFloorMultiplier = g.absoluteFloorMultiplier
            if g.absoluteCeilingMultiplier is not None:
                org.settings.guardrails.absoluteCeilingMultiplier = g.absoluteCeilingMultiplier
        if req.settings.automation:
            a = req.settings.automation
            if a.autoPushApproved is not None:
                org.settings.automation.autoPushApproved = a.autoPushApproved
            if a.dailyPipelineRun is not None:
                org.settings.automation.dailyPipelineRun = a.dailyPipelineRun
        if req.settings.overrides:
            o = req.settings.overrides
            if o.currency is not None:
                org.settings.overrides.currency = o.currency
            if o.timezone is not None:
                org.settings.overrides.timezone = o.timezone
            if o.weekendDefinition is not None:
                org.settings.overrides.weekendDefinition = o.weekendDefinition

    await org.save()
    return {"success": True}


@markets_router.get("/")
async def get_markets():
    db_markets = await MarketTemplate.find(MarketTemplate.isActive == True).sort(+MarketTemplate.displayName).to_list()
    if db_markets:
        return {
            "success": True,
            "markets": [
                {
                    "code": m.marketCode,
                    "name": m.displayName,
                    "country": m.country,
                    "currency": m.currency,
                    "timezone": m.timezone,
                    "weekend": m.weekendDefinition,
                    "flag": m.flag,
                }
                for m in db_markets
            ],
        }

    return {
        "success": True,
        "markets": [
            {"code": "UAE_DXB", "name": "Dubai", "country": "UAE", "currency": "AED", "timezone": "Asia/Dubai", "weekend": "fri_sat", "flag": "🇦🇪"},
            {"code": "GBR_LON", "name": "London", "country": "UK", "currency": "GBP", "timezone": "Europe/London", "weekend": "sat_sun", "flag": "🇬🇧"},
            {"code": "USA_NYC", "name": "New York", "country": "USA", "currency": "USD", "timezone": "America/New_York", "weekend": "sat_sun", "flag": "🇺🇸"},
        ],
    }
