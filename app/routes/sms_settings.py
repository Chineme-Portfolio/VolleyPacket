from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel

from app.database import get_session, UserRow, SMSSettingsRow
from app.dependencies import get_current_user
from app.services.encryption import encrypt_credentials, decrypt_credentials
from app.services.sms_providers import create_sms_provider, PROVIDERS, PROVIDER_FIELDS, SmsMessage
from app.services.sms_providers.phone import to_e164

router = APIRouter()


# ── Request / Response models ─────────────────────────────────────────


class SaveSmsSettingsRequest(BaseModel):
    provider_name: str  # "bulksms", "twilio", "vonage", "termii", "africastalking"
    credentials: dict   # provider-specific, e.g. {"account_sid": "...", "auth_token": "..."}
    sender_id: str
    default_region: str = "NG"


class SmsSettingsResponse(BaseModel):
    provider_name: str
    sender_id: str
    default_region: str
    is_configured: bool


class TestSmsRequest(BaseModel):
    to: str


# ── Routes ────────────────────────────────────────────────────────────


@router.get("/providers")
def list_providers():
    """List supported SMS providers and the credential fields each expects."""
    return {"providers": list(PROVIDERS.keys()), "fields": PROVIDER_FIELDS}


@router.post("")
def save_sms_settings(req: SaveSmsSettingsRequest, user: UserRow = Depends(get_current_user)):
    """Save or update the user's SMS provider settings."""
    try:
        provider = create_sms_provider(req.provider_name, req.credentials)
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
        existing = session.get(SMSSettingsRow, user.id)
        if existing:
            existing.provider_name = req.provider_name
            existing.credentials_encrypted = encrypted
            existing.sender_id = req.sender_id
            existing.default_region = req.default_region or "NG"
            existing.updated_at = datetime.utcnow()
        else:
            session.add(SMSSettingsRow(
                user_id=user.id,
                provider_name=req.provider_name,
                credentials_encrypted=encrypted,
                sender_id=req.sender_id,
                default_region=req.default_region or "NG",
            ))
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    return {"message": "SMS settings saved"}


@router.get("", response_model=SmsSettingsResponse)
def get_sms_settings(user: UserRow = Depends(get_current_user)):
    """Get the user's current SMS provider config (without credentials)."""
    session = get_session()
    try:
        settings = session.get(SMSSettingsRow, user.id)
        if not settings:
            return SmsSettingsResponse(provider_name="", sender_id="", default_region="NG", is_configured=False)
        return SmsSettingsResponse(
            provider_name=settings.provider_name,
            sender_id=settings.sender_id,
            default_region=settings.default_region,
            is_configured=True,
        )
    finally:
        session.close()


@router.delete("")
def delete_sms_settings(user: UserRow = Depends(get_current_user)):
    """Remove the user's SMS settings."""
    session = get_session()
    try:
        settings = session.get(SMSSettingsRow, user.id)
        if settings:
            session.delete(settings)
            session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    return {"message": "SMS settings removed"}


@router.post("/test")
def test_sms_settings(req: TestSmsRequest, user: UserRow = Depends(get_current_user)):
    """Send a test SMS to a number the user provides, using their saved config."""
    session = get_session()
    try:
        settings = session.get(SMSSettingsRow, user.id)
    finally:
        session.close()

    if not settings:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No SMS settings configured")

    numbers = to_e164(req.to, settings.default_region)
    if not numbers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Enter a valid phone number to test (e.g. +234… or a local number for your default region).",
        )

    credentials = decrypt_credentials(settings.credentials_encrypted)
    provider = create_sms_provider(settings.provider_name, credentials)

    try:
        provider.send(SmsMessage(
            to=numbers[0],
            body="VolleyPacket — your SMS settings are working correctly.",
            sender_id=settings.sender_id,
        ))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Test SMS failed: {str(e)}")

    return {"message": f"Test SMS sent to {numbers[0]}"}
