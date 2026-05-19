from app.services.email_providers.base import EmailProvider, EmailMessage
from app.services.email_providers.resend_provider import ResendProvider
from app.services.email_providers.sendgrid_provider import SendGridProvider
from app.services.email_providers.smtp_provider import SMTPProvider


# Registry: provider name -> class
PROVIDERS: dict[str, type[EmailProvider]] = {
    "resend": ResendProvider,
    "sendgrid": SendGridProvider,
    "smtp": SMTPProvider,
}

# Preset SMTP configs for known services
SMTP_PRESETS: dict[str, dict] = {
    "gmail": {"host": "smtp.gmail.com", "port": 587, "use_tls": True},
    "zoho": {"host": "smtp.zoho.com", "port": 587, "use_tls": True},
    "outlook": {"host": "smtp-mail.outlook.com", "port": 587, "use_tls": True},
    "yahoo": {"host": "smtp.mail.yahoo.com", "port": 587, "use_tls": True},
}


def create_provider(provider_name: str, credentials: dict) -> EmailProvider:
    """
    Factory to create an email provider from a name and credentials dict.

    API providers (resend, sendgrid):
        {"api_key": "..."}

    SMTP providers (smtp, gmail, zoho, outlook, yahoo):
        {"username": "...", "password": "..."}
        For generic smtp also: {"host": "...", "port": 587}
    """
    # Check if it's an SMTP preset (gmail, zoho, etc.)
    if provider_name in SMTP_PRESETS:
        preset = SMTP_PRESETS[provider_name]
        return SMTPProvider(
            host=preset["host"],
            port=preset["port"],
            username=credentials["username"],
            password=credentials["password"],
            use_tls=preset.get("use_tls", True),
        )

    # Check the provider registry
    if provider_name not in PROVIDERS:
        available = list(PROVIDERS.keys()) + list(SMTP_PRESETS.keys())
        raise ValueError(f"Unknown provider '{provider_name}'. Available: {available}")

    cls = PROVIDERS[provider_name]

    if cls == SMTPProvider:
        return SMTPProvider(
            host=credentials["host"],
            port=int(credentials.get("port", 587)),
            username=credentials["username"],
            password=credentials["password"],
            use_tls=credentials.get("use_tls", True),
        )

    # API-based providers
    return cls(api_key=credentials["api_key"])
