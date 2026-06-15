"""
Authentication: password hashing, JWT tokens, Google OAuth verification.
"""

import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
import requests

from app import config
from app.database import get_session, UserRow


# ── Password hashing ──────────────────────────────────────────────────


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


# ── JWT ───────────────────────────────────────────────────────────────


def create_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=config.JWT_EXPIRY_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, config.SECRET_KEY, algorithm=config.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT. Raises jwt.InvalidTokenError on failure."""
    return jwt.decode(token, config.SECRET_KEY, algorithms=[config.JWT_ALGORITHM])


# ── Google OAuth ──────────────────────────────────────────────────────


def verify_google_token(id_token: str) -> dict:
    """
    Verify a Google ID token using Google's tokeninfo endpoint.
    Returns the token payload with email, name, etc.
    Raises ValueError on invalid token.
    """
    resp = requests.get(
        "https://oauth2.googleapis.com/tokeninfo",
        params={"id_token": id_token},
        timeout=10,
    )

    if resp.status_code != 200:
        raise ValueError("Invalid Google token")

    payload = resp.json()

    # Verify the token was issued for our app
    if not config.GOOGLE_CLIENT_ID:
        raise ValueError("Google OAuth is not configured (GOOGLE_CLIENT_ID is missing)")
    if payload.get("aud") != config.GOOGLE_CLIENT_ID:
        raise ValueError("Google token audience mismatch")

    if payload.get("email_verified") != "true":
        raise ValueError("Google email not verified")

    return payload


# ── User CRUD ─────────────────────────────────────────────────────────


def create_user(email: str, password: str | None = None, auth_provider: str = "local") -> UserRow:
    session = get_session()
    try:
        user = UserRow(
            id=str(uuid.uuid4()),
            email=email.lower().strip(),
            password_hash=hash_password(password) if password else None,
            auth_provider=auth_provider,
            created_at=datetime.utcnow(),
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_user_by_email(email: str) -> UserRow | None:
    session = get_session()
    try:
        return session.query(UserRow).filter(UserRow.email == email.lower().strip()).first()
    finally:
        session.close()


def get_user_by_id(user_id: str) -> UserRow | None:
    session = get_session()
    try:
        return session.get(UserRow, user_id)
    finally:
        session.close()


def update_user(user_id: str, **fields) -> UserRow | None:
    """Update arbitrary columns on a user. Returns the refreshed row, or None if not found."""
    session = get_session()
    try:
        user = session.get(UserRow, user_id)
        if not user:
            return None
        for key, value in fields.items():
            if hasattr(user, key):
                setattr(user, key, value)
        session.commit()
        session.refresh(user)
        return user
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
