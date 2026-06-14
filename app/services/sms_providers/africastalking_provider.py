import requests

from app.services.sms_providers.base import SmsProvider, SmsMessage


class AfricasTalkingProvider(SmsProvider):
    """Africa's Talking (https://africastalking.com). Africa-focused."""

    name = "africastalking"

    API_URL = "https://api.africastalking.com/version1/messaging"

    def __init__(self, username: str, api_key: str):
        self.username = username
        self.api_key = api_key

    def validate_config(self) -> bool:
        return bool(self.username and self.api_key)

    def send(self, message: SmsMessage) -> None:
        # Africa's Talking wants E.164 (keep the "+"). "from" (sender ID) is optional.
        data = {"username": self.username, "to": message.to, "message": message.body}
        if message.sender_id:
            data["from"] = message.sender_id
        resp = requests.post(
            self.API_URL,
            data=data,
            headers={
                "apiKey": self.api_key,
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            timeout=30,
        )
        if resp.status_code >= 400:
            raise Exception(f"Africa's Talking error {resp.status_code}: {resp.text}")
        try:
            recipients = resp.json().get("SMSMessageData", {}).get("Recipients", [])
        except Exception:
            recipients = []
        if recipients and recipients[0].get("status") != "Success":
            raise Exception(f"Africa's Talking error: {recipients[0].get('status')}")
