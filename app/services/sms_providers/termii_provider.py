import requests

from app.services.sms_providers.base import SmsProvider, SmsMessage


class TermiiProvider(SmsProvider):
    """Termii (https://termii.com). Africa-focused."""

    name = "termii"

    API_URL = "https://api.ng.termii.com/api/sms/send"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def validate_config(self) -> bool:
        return bool(self.api_key)

    def send(self, message: SmsMessage) -> None:
        # Termii wants the number without a leading "+".
        to = message.to.lstrip("+")
        resp = requests.post(
            self.API_URL,
            json={
                "to": to,
                "from": message.sender_id,
                "sms": message.body,
                "type": "plain",
                "channel": "generic",
                "api_key": self.api_key,
            },
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=30,
        )
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("message", resp.text)
            except Exception:
                detail = resp.text
            raise Exception(f"Termii error {resp.status_code}: {detail}")
