import requests
from requests.auth import HTTPBasicAuth

from app.services.sms_providers.base import SmsProvider, SmsMessage


class TwilioProvider(SmsProvider):
    """Twilio (https://www.twilio.com). Global. REST API, HTTP Basic auth."""

    name = "twilio"

    def __init__(self, account_sid: str, auth_token: str):
        self.account_sid = account_sid
        self.auth_token = auth_token

    def validate_config(self) -> bool:
        return bool(self.account_sid and self.auth_token)

    def send(self, message: SmsMessage) -> None:
        # Twilio wants E.164 (keep the "+"). "From" is a Twilio number or Messaging Service SID.
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"
        resp = requests.post(
            url,
            data={"To": message.to, "From": message.sender_id, "Body": message.body},
            auth=HTTPBasicAuth(self.account_sid, self.auth_token),
            timeout=30,
        )
        if resp.status_code >= 400:
            raise Exception(f"Twilio error {resp.status_code}: {resp.text}")
