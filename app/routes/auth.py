from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, EmailStr

from app.services.auth import (
    create_user,
    get_user_by_email,
    verify_password,
    create_token,
    verify_google_token,
)
from app.dependencies import get_current_user
from app.database import UserRow

router = APIRouter()


# ── Request / Response models ─────────────────────────────────────────


class SignupRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class GoogleLoginRequest(BaseModel):
    id_token: str


class AuthResponse(BaseModel):
    token: str
    user: dict


class UserResponse(BaseModel):
    id: str
    email: str
    auth_provider: str
    tier: str = "free"


# ── Routes ────────────────────────────────────────────────────────────


@router.post("/signup", response_model=AuthResponse)
def signup(req: SignupRequest):
    existing = get_user_by_email(req.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    if len(req.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters",
        )

    user = create_user(email=req.email, password=req.password, auth_provider="local")
    token = create_token(user.id, user.email)

    return AuthResponse(
        token=token,
        user={"id": user.id, "email": user.email, "auth_provider": user.auth_provider, "tier": getattr(user, "tier", "free") or "free"},
    )


@router.post("/login", response_model=AuthResponse)
def login(req: LoginRequest):
    user = get_user_by_email(req.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if user.auth_provider != "local":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"This account uses {user.auth_provider} login",
        )

    if not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_token(user.id, user.email)

    return AuthResponse(
        token=token,
        user={"id": user.id, "email": user.email, "auth_provider": user.auth_provider, "tier": getattr(user, "tier", "free") or "free"},
    )


@router.post("/google", response_model=AuthResponse)
def google_login(req: GoogleLoginRequest):
    try:
        google_payload = verify_google_token(req.id_token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )

    email = google_payload["email"]
    user = get_user_by_email(email)

    if not user:
        # Auto-create account on first Google login
        user = create_user(email=email, password=None, auth_provider="google")

    token = create_token(user.id, user.email)

    return AuthResponse(
        token=token,
        user={"id": user.id, "email": user.email, "auth_provider": user.auth_provider, "tier": getattr(user, "tier", "free") or "free"},
    )


@router.get("/me", response_model=UserResponse)
def get_me(user: UserRow = Depends(get_current_user)):
    return UserResponse(
        id=user.id,
        email=user.email,
        auth_provider=user.auth_provider,
        tier=getattr(user, "tier", "free") or "free",
    )
