import secrets
import string
from typing import Optional, Literal

from beanie import PydanticObjectId
from fastapi import APIRouter, HTTPException
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr

from app.models.organization import Organization
from app.models.user import User

admin_router = APIRouter(prefix="/admin", tags=["admin"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def generate_temp_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    base = "".join(secrets.choice(alphabet) for _ in range(max(8, length - 3)))
    return f"{base}A1!"


class CreateUserRequest(BaseModel):
    fullName: str
    email: EmailStr
    role: Literal["owner", "admin", "viewer"] = "viewer"
    marketCode: Optional[str] = "UAE_DXB"
    skipOnboarding: bool = False
    temporaryPassword: Optional[str] = None


class PatchUserRequest(BaseModel):
    userId: str
    isApproved: Optional[bool] = None
    role: Optional[Literal["owner", "admin", "viewer"]] = None
    onboardingStep: Optional[Literal["connect", "select", "market", "strategy", "complete"]] = None


@admin_router.get("/users")
async def list_users():
    orgs = await Organization.find_all().sort(-Organization.createdAt).to_list()
    users = [
        {
            "id": str(o.id),
            "name": o.fullName or o.name,
            "email": o.email,
            "role": o.role,
            "isApproved": o.isApproved,
            "marketCode": o.marketCode,
            "currency": o.currency,
            "plan": o.plan,
            "createdAt": o.createdAt.isoformat() if o.createdAt else None,
            "onboardingStep": o.onboarding.step if o.onboarding else "complete",
        }
        for o in orgs
    ]
    return {"users": users}


@admin_router.post("/users")
async def create_user(req: CreateUserRequest):
    email = req.email.strip().lower()
    existing_org = await Organization.find_one(Organization.email == email)
    existing_user = await User.find_one(User.email == email)
    if existing_org or existing_user:
        raise HTTPException(status_code=409, detail="A user with this email already exists")

    raw_password = req.temporaryPassword or generate_temp_password()
    onboarding_step = "complete" if req.skipOnboarding else "connect"

    org = Organization(
        name=req.fullName,
        fullName=req.fullName,
        email=email,
        passwordHash=hash_password(raw_password),
        role=req.role,
        isApproved=True,
        marketCode=req.marketCode or "UAE_DXB",
        onboarding={"step": onboarding_step},
    )
    await org.insert()

    return {
        "success": True,
        "user": {
            "id": str(org.id),
            "email": org.email,
            "name": org.fullName or org.name,
            "role": org.role,
            "temporaryPassword": raw_password,
        },
    }


@admin_router.patch("/users")
async def patch_user(req: PatchUserRequest):
    try:
        oid = PydanticObjectId(req.userId)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid userId")

    org = await Organization.get(oid)
    if not org:
        raise HTTPException(status_code=404, detail="User not found")

    if req.isApproved is not None:
        org.isApproved = req.isApproved
    if req.role is not None:
        org.role = req.role
    if req.onboardingStep is not None:
        if org.onboarding:
            org.onboarding.step = req.onboardingStep
        else:
            org.onboarding = {"step": req.onboardingStep}
        if req.onboardingStep == "complete" and org.onboarding:
            from datetime import datetime, timezone
            org.onboarding.completedAt = datetime.now(timezone.utc)

    await org.save()
    return {"success": True}


@admin_router.post("/users/{user_id}/approve")
async def approve_user(user_id: str, body: dict | None = None):
    try:
        oid = PydanticObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user id")

    org = await Organization.get(oid)
    if not org:
        raise HTTPException(status_code=404, detail="User not found")

    approve = True
    if body and body.get("approve") is False:
        approve = False

    org.isApproved = approve
    await org.save()

    return {
        "success": True,
        "id": str(org.id),
        "email": org.email,
        "isApproved": org.isApproved,
    }
