from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel

from app.database import get_session, UserRow, EmailSettingsRow
from app.dependencies import get_current_user
from app.services.encryption import encrypt_credentials, decrypt_credentials
from app.services.email_providers import create_provider, PROVIDERS, SMTP_PRESETS

router = APIRouter()


# ── Request / Response models ─────────────────────────────────────────


class SaveEmailSettingsRequest(BaseModel):
    provider_name: str  # "resend", "sendgrid", "gmail", "zoho", "smtp", etc.
    credentials: dict   # {"api_key": "..."} or {"username": "...", "password": "...", ...}
    from_name: str
    from_email: str


class EmailSettingsResponse(BaseModel):
    provider_name: str
    from_name: str
    from_email: str
    is_configured: bool


class AvailableProvidersResponse(BaseModel):
    api_providers: list[str]
    smtp_presets: list[str]


# ── Routes ────────────────────────────────────────────────────────────


@router.get("/providers", response_model=AvailableProvidersResponse)
def list_providers():
    """List all supported email providers."""
    return AvailableProvidersResponse(
        api_providers=[k for k in PROVIDERS.keys() if k != "smtp"],
        smtp_presets=list(SMTP_PRESETS.keys()) + ["smtp"],
    )


@router.post("")
def save_email_settings(req: SaveEmailSettingsRequest, user: UserRow = Depends(get_current_user)):
    """Save or update the user's email provider settings."""
    # Validate by trying to create the provider
    try:
        provider = create_provider(req.provider_name, req.credentials)
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    if not provider.validate_config():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid credentials for this provider",
        )

    encrypted = encrypt_credentials(req.credentials)

    session = get_session()
    try:
        existing = session.get(EmailSettingsRow, user.id)
        if existing:
            existing.provider_name = req.provider_name
            existing.credentials_encrypted = encrypted
            existing.from_name = req.from_name
            existing.from_email = req.from_email
            existing.updated_at = datetime.utcnow()
        else:
            session.add(EmailSettingsRow(
                user_id=user.id,
                provider_name=req.provider_name,
                credentials_encrypted=encrypted,
                from_name=req.from_name,
                from_email=req.from_email,
            ))
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    return {"message": "Email settings saved"}


@router.get("", response_model=EmailSettingsResponse)
def get_email_settings(user: UserRow = Depends(get_current_user)):
    """Get the user's current email provider config (without credentials)."""
    session = get_session()
    try:
        settings = session.get(EmailSettingsRow, user.id)
        if not settings:
            return EmailSettingsResponse(
                provider_name="",
                from_name="",
                from_email="",
                is_configured=False,
            )
        return EmailSettingsResponse(
            provider_name=settings.provider_name,
            from_name=settings.from_name,
            from_email=settings.from_email,
            is_configured=True,
        )
    finally:
        session.close()


@router.delete("")
def delete_email_settings(user: UserRow = Depends(get_current_user)):
    """Remove the user's email settings."""
    session = get_session()
    try:
        settings = session.get(EmailSettingsRow, user.id)
        if settings:
            session.delete(settings)
            session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    return {"message": "Email settings removed"}


@router.post("/test")
def test_email_settings(user: UserRow = Depends(get_current_user)):
    """Send a test email to the user's own address using their saved config."""
    session = get_session()
    try:
        settings = session.get(EmailSettingsRow, user.id)
    finally:
        session.close()

    if not settings:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No email settings configured",
        )

    credentials = decrypt_credentials(settings.credentials_encrypted)
    provider = create_provider(settings.provider_name, credentials)

    from app.services.email_providers.base import EmailMessage

    try:
        provider.send(EmailMessage(
            from_name=settings.from_name,
            from_email=settings.from_email,
            to=user.email,
            subject="VolleyPacket — Test Email",
            html="<p>Your email settings are working correctly.</p>",
        ))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Test email failed: {str(e)}",
        )

    return {"message": f"Test email sent to {user.email}"}
