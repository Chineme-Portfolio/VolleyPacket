import io
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File
from pydantic import BaseModel, EmailStr

from app.services.auth import (
    create_user,
    get_user_by_email,
    get_user_by_id,
    update_user,
    verify_password,
    create_token,
    verify_google_token,
)
from app.dependencies import get_current_user
from app.database import get_session, UserRow, SubscriptionRow, TemplateRow
from app.services.storage import store

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
    username: str = ""
    avatar: Optional[str] = None


class UpdateProfileRequest(BaseModel):
    username: Optional[str] = None
    avatar: Optional[str] = None


# Preset avatar ids the client can render (animals + alien + silhouettes)
PRESET_AVATARS = {
    "koala", "panda", "bear", "kangaroo", "dog", "cat", "mouse", "alien",
    "silhouette-male", "silhouette-female", "silhouette-nb",
}


def _display_name(user: UserRow) -> str:
    """Username if set, else the email local-part (matches legacy template attribution)."""
    return (getattr(user, "username", None) or "").strip() or user.email.split("@")[0]


def _user_response(user: UserRow) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        auth_provider=user.auth_provider,
        tier=getattr(user, "tier", "free") or "free",
        username=_display_name(user),
        avatar=getattr(user, "avatar", None),
    )


def _propagate_owner(user: UserRow) -> None:
    """Keep this user's public-template attribution in sync with their profile."""
    session = get_session()
    try:
        session.query(TemplateRow).filter(TemplateRow.owner_id == user.id).update(
            {
                TemplateRow.owner_name: _display_name(user),
                TemplateRow.owner_avatar: getattr(user, "avatar", None),
            },
            synchronize_session=False,
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


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
        user=_user_response(user).model_dump(),
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
        user=_user_response(user).model_dump(),
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
        user=_user_response(user).model_dump(),
    )


@router.get("/me", response_model=UserResponse)
def get_me(user: UserRow = Depends(get_current_user)):
    return _user_response(user)


@router.patch("/me", response_model=UserResponse)
def update_me(req: UpdateProfileRequest, user: UserRow = Depends(get_current_user)):
    """Update the display name and/or avatar. Keeps public-template attribution in sync."""
    fields = {}
    if req.username is not None:
        fields["username"] = req.username.strip()[:50] or None
    if req.avatar is not None:
        av = req.avatar.strip()
        if av == "":
            fields["avatar"] = None
        elif av.startswith("preset:") and av.split(":", 1)[1] in PRESET_AVATARS:
            fields["avatar"] = av
        else:
            raise HTTPException(status_code=400, detail="Invalid avatar selection")
    if fields:
        updated = update_user(user.id, **fields)
        if not updated:
            raise HTTPException(status_code=404, detail="User not found")
        user = updated
        _propagate_owner(user)
    return _user_response(user)


@router.post("/me/avatar", response_model=UserResponse)
async def upload_avatar(file: UploadFile = File(...), user: UserRow = Depends(get_current_user)):
    """Upload a custom avatar. Normalized to a 256² PNG and stored for public serving."""
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Avatar too large (max 5 MB)")

    is_png = content[:8] == b"\x89PNG\r\n\x1a\n"
    is_jpg = content[:2] == b"\xff\xd8"
    is_webp = content[:4] == b"RIFF" and content[8:12] == b"WEBP"
    if not (is_png or is_jpg or is_webp):
        raise HTTPException(status_code=400, detail="Avatar must be a PNG, JPEG, or WEBP image")

    try:
        from PIL import Image

        img = Image.open(io.BytesIO(content)).convert("RGBA")
        w, h = img.size
        side = min(w, h)
        left, top = (w - side) // 2, (h - side) // 2
        resample = getattr(Image, "Resampling", Image).LANCZOS
        img = img.crop((left, top, left + side, top + side)).resize((256, 256), resample)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png_bytes = buf.getvalue()
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not process image: {e}")

    store.save_bytes(f"avatars/{user.id}.png", png_bytes)
    updated = update_user(user.id, avatar=f"upload:{uuid.uuid4().hex[:8]}")
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")
    _propagate_owner(updated)
    return _user_response(updated)


@router.get("/avatar/{user_id}")
def get_avatar(user_id: str):
    """Public — serve a user's uploaded avatar PNG so it shows on their public templates.
    Presets and the initials fallback are rendered client-side, so only uploads hit this."""
    key = f"avatars/{user_id}.png"
    if not store.exists(key):
        raise HTTPException(status_code=404, detail="No avatar")
    return store.serve_inline(key, "image/png")


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
