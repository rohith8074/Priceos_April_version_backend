import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Request
from pydantic import BaseModel
from passlib.context import CryptContext
from jose import JWTError, jwt

from app.models.user import User
from app.models.organization import Organization

SECRET_KEY = os.environ.get("JWT_SECRET", "super-secret-key-for-priceos-dev-only")
REFRESH_SECRET = os.environ.get("JWT_REFRESH_SECRET", "priceos-refresh-secret-dev-only")
ALGORITHM = "HS256"
ACCESS_EXPIRE_MINUTES = 60 * 24 * 7   # 7 days
REFRESH_EXPIRE_MINUTES = 60 * 24 * 30  # 30 days

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
auth_router = APIRouter(prefix="/auth", tags=["auth"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str

class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str
    orgName: Optional[str] = None

class RefreshRequest(BaseModel):
    refreshToken: str


# ── Helpers ────────────────────────────────────────────────────────────────────

def normalize_email(email: str) -> str:
    return email.strip().lower()

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)

def make_access_token(payload: dict) -> str:
    data = {**payload, "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_EXPIRE_MINUTES)}
    return jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)

def make_refresh_token(user_id: str) -> str:
    data = {"userId": user_id, "exp": datetime.now(timezone.utc) + timedelta(minutes=REFRESH_EXPIRE_MINUTES)}
    return jwt.encode(data, REFRESH_SECRET, algorithm=ALGORITHM)


async def find_auth_subject_by_email(email: str):
    normalized = normalize_email(email)
    user = await User.find_one(User.email == normalized)
    if user:
        return "user", user
    org = await Organization.find_one(Organization.email == normalized)
    if org:
        return "organization", org
    return None, None


# ── Endpoints ──────────────────────────────────────────────────────────────────

@auth_router.post("/login")
async def login(req: LoginRequest):
    normalized_email = normalize_email(req.email)
    subject_type, subject = await find_auth_subject_by_email(normalized_email)
    if not subject or not subject.passwordHash or not verify_password(req.password, subject.passwordHash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    org_id = None
    role = "owner"
    is_approved = True
    onboarding_step = "complete"

    if subject_type == "user":
        user = subject
        org_id = str(user.orgId) if user.orgId else None
        if not org_id:
            org = await Organization.find_one(Organization.email == user.email)
            if not org:
                org = await Organization.find_one({})
            if org:
                org_id = str(org.id)
        role = user.role or "owner"
        is_approved = user.isApproved if user.isApproved is not None else True
        onboarding_step = user.onboardingStep or "complete"
    else:
        org = subject
        org_id = str(org.id)
        role = org.role or "owner"
        is_approved = org.isApproved if org.isApproved is not None else True
        onboarding_step = org.onboarding.step if getattr(org, "onboarding", None) else "complete"

    payload = {
        "sub": normalized_email,
        "userId": str(subject.id),
        "orgId": org_id or "",
        "email": normalized_email,
        "role": role,
        "isApproved": is_approved,
        "onboardingStep": onboarding_step,
    }

    return {
        "accessToken": make_access_token(payload),
        "refreshToken": make_refresh_token(str(subject.id)),
        "user": payload,
    }



@auth_router.post("/register")
async def register(req: RegisterRequest):
    normalized_email = normalize_email(req.email)
    existing_user = await User.find_one(User.email == normalized_email)
    existing_org = await Organization.find_one(Organization.email == normalized_email)
    existing = existing_user or existing_org
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    # Create or find a default org
    org_name = req.orgName or f"{req.name}'s Organization"
    org = Organization(name=org_name)
    await org.insert()

    user = User(
        email=normalized_email,
        passwordHash=hash_password(req.password),
        name=req.name,
        orgId=org.id,
        role="admin",
    )
    await user.insert()

    return {"success": True, "message": "Registration successful. Please wait for approval."}


@auth_router.post("/refresh")
async def refresh_token(req: RefreshRequest):
    try:
        data = jwt.decode(req.refreshToken, REFRESH_SECRET, algorithms=[ALGORITHM])
        user_id = data.get("userId")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    from beanie import PydanticObjectId
    oid = PydanticObjectId(user_id)
    user = await User.get(oid)
    if user:
        payload = {
            "sub": user.email,
            "userId": str(user.id),
            "orgId": str(user.orgId) if user.orgId else "",
            "email": user.email,
            "role": user.role or "user",
            "isApproved": user.isApproved if hasattr(user, "isApproved") else True,
            "onboardingStep": user.onboardingStep if hasattr(user, "onboardingStep") else "complete",
        }
    else:
        org = await Organization.get(oid)
        if not org:
            raise HTTPException(status_code=401, detail="User not found")
        payload = {
            "sub": org.email,
            "userId": str(org.id),
            "orgId": str(org.id),
            "email": org.email,
            "role": org.role or "owner",
            "isApproved": org.isApproved if hasattr(org, "isApproved") else True,
            "onboardingStep": org.onboarding.step if hasattr(org, "onboarding") and org.onboarding else "complete",
        }

    return {"accessToken": make_access_token(payload)}


@auth_router.get("/check-approval")
async def check_approval(userId: str):
    from beanie import PydanticObjectId
    try:
        oid = PydanticObjectId(userId)
        user = await User.get(oid)
    except Exception:
        raise HTTPException(status_code=404, detail="User not found")

    if user:
        is_approved = user.isApproved if hasattr(user, "isApproved") else True
        return {"approved": is_approved, "onboardingStep": getattr(user, "onboardingStep", "complete")}

    org = await Organization.get(oid)
    if not org:
        raise HTTPException(status_code=404, detail="User not found")
    is_approved = org.isApproved if hasattr(org, "isApproved") else True
    onboarding_step = org.onboarding.step if hasattr(org, "onboarding") and org.onboarding else "complete"
    return {"approved": is_approved, "onboardingStep": onboarding_step}


@auth_router.get("/admin-reset-password")
async def check_reset_email(email: str):
    normalized_email = normalize_email(email)
    subject_type, subject = await find_auth_subject_by_email(normalized_email)
    if not subject:
        return {"exists": False}
    display_name = getattr(subject, "name", None) or getattr(subject, "fullName", None) or normalized_email
    return {"exists": True, "name": display_name, "source": subject_type}


@auth_router.post("/admin-reset-password")
async def reset_password(body: dict):
    email = body.get("email")
    new_password = body.get("password")
    if not email or not new_password:
        raise HTTPException(status_code=400, detail="email and password required")

    normalized_email = normalize_email(email)
    _, subject = await find_auth_subject_by_email(normalized_email)
    if not subject:
        raise HTTPException(status_code=404, detail="User not found")

    subject.passwordHash = hash_password(new_password)
    await subject.save()
    return {"success": True, "message": "Password updated"}
