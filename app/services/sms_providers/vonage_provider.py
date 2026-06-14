import requests

from app.services.sms_providers.base import SmsProvider, SmsMessage


class VonageProvider(SmsProvider):
    """Vonage / Nexmo (https://www.vonage.com). Global."""

    name = "vonage"

    API_URL = "https://rest.nexmo.com/sms/json"

    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret

    def validate_config(self) -> bool:
        return bool(self.api_key and self.api_secret)

    def send(self, message: SmsMessage) -> None:
        # Vonage wants the number without a leading "+".
        to = message.to.lstrip("+")
        resp = requests.post(
            self.API_URL,
            data={
                "api_key": self.api_key,
                "api_secret": self.api_secret,
                "to": to,
                "from": message.sender_id,
                "text": message.body,
            },
            timeout=30,
        )
        try:
            msgs = resp.json().get("messages", [])
        except Exception:
            msgs = []
        # Vonage returns one entry per message-part; status "0" == success.
        if not msgs or msgs[0].get("status") != "0":
            err = msgs[0].get("error-text", "Unknown error") if msgs else f"HTTP {resp.status_code}"
            raise Exception(f"Vonage error: {err}")
