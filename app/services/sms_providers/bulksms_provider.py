import requests

from app.services.sms_providers.base import SmsProvider, SmsMessage
from app import config


class BulkSmsProvider(SmsProvider):
    """BulkSMS Nigeria (https://www.bulksmsnigeria.com). Nigeria-focused."""

    name = "bulksms"

    def __init__(self, api_token: str, api_url: str = ""):
        self.api_token = api_token
        self.api_url = api_url or config.BULKSMS_API_URL

    def validate_config(self) -> bool:
        return bool(self.api_token)

    def send(self, message: SmsMessage) -> None:
        # BulkSMS expects the number without a leading "+".
        to = message.to.lstrip("+")
        resp = requests.post(
            self.api_url,
            json={"from": message.sender_id, "to": to, "body": message.body},
            headers={
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=30,
        )
        try:
            data = resp.json()
        except Exception:
            data = {}
        if data.get("status") == "success":
            return
        error = (data.get("error") or {}).get("message") or data.get("message") or f"HTTP {resp.status_code}"
        raise Exception(f"BulkSMS error: {error}")
