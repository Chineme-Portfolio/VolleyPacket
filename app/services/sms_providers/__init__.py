from app.services.sms_providers.base import SmsProvider, SmsMessage
from app.services.sms_providers.phone import to_e164
from app.services.sms_providers.bulksms_provider import BulkSmsProvider
from app.services.sms_providers.twilio_provider import TwilioProvider
from app.services.sms_providers.vonage_provider import VonageProvider
from app.services.sms_providers.termii_provider import TermiiProvider
from app.services.sms_providers.africastalking_provider import AfricasTalkingProvider


# Registry: provider name -> class
PROVIDERS: dict[str, type[SmsProvider]] = {
    "bulksms": BulkSmsProvider,
    "twilio": TwilioProvider,
    "vonage": VonageProvider,
    "termii": TermiiProvider,
    "africastalking": AfricasTalkingProvider,
}

# Credential keys each provider expects (the settings UI mirrors these per provider).
PROVIDER_FIELDS: dict[str, list[str]] = {
    "bulksms": ["api_token"],
    "twilio": ["account_sid", "auth_token"],
    "vonage": ["api_key", "api_secret"],
    "termii": ["api_key"],
    "africastalking": ["username", "api_key"],
}


def create_sms_provider(provider_name: str, credentials: dict) -> SmsProvider:
    """Factory: build an SMS provider from a name + credentials dict (mirrors create_provider)."""
    if provider_name not in PROVIDERS:
        raise ValueError(f"Unknown SMS provider '{provider_name}'. Available: {list(PROVIDERS)}")

    if provider_name == "bulksms":
        return BulkSmsProvider(api_token=credentials["api_token"])
    if provider_name == "twilio":
        return TwilioProvider(account_sid=credentials["account_sid"], auth_token=credentials["auth_token"])
    if provider_name == "vonage":
        return VonageProvider(api_key=credentials["api_key"], api_secret=credentials["api_secret"])
    if provider_name == "termii":
        return TermiiProvider(api_key=credentials["api_key"])
    if provider_name == "africastalking":
        return AfricasTalkingProvider(username=credentials["username"], api_key=credentials["api_key"])

    raise ValueError(f"Unknown SMS provider '{provider_name}'")
