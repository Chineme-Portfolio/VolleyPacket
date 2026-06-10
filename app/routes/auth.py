import logging

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
from app.database import get_session, UserRow, SubscriptionRow

router = APIRouter()
logger = logging.getLogger(__name__)


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


@router.delete("/me")
def delete_account(user: UserRow = Depends(get_current_user)):
    """Permanently delete the account and all associated data.

    Any active paid subscription is cancelled with the payment provider
    first so billing stops — if that fails, the deletion is aborted so
    the user is never left paying for a deleted account.
    """
    session = get_session()
    try:
        sub = session.query(SubscriptionRow).filter_by(user_id=user.id).first()
        has_paid_sub = bool(sub and sub.tier != "free" and sub.status == "active")
    finally:
        session.close()

    if has_paid_sub:
        # Imported here to avoid a circular import at module load
        from app.routes.billing import _cancel_at_provider

        _cancel_at_provider(sub, immediately=True)
        logger.info(f"Cancelled {sub.payment_provider} subscription for {user.id} before account deletion")

    session = get_session()
    try:
        row = session.get(UserRow, user.id)
        if row:
            session.delete(row)  # jobs, templates, subscriptions cascade
            session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    logger.info(f"Account deleted: {user.id} ({user.email})")
    return {"message": "Account deleted."}
