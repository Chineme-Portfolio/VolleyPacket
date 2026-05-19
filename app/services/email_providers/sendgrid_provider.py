import base64
import requests

from app.services.email_providers.base import EmailProvider, EmailMessage


class SendGridProvider(EmailProvider):
    name = "sendgrid"

    API_URL = "https://api.sendgrid.com/v3/mail/send"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def validate_config(self) -> bool:
        return bool(self.api_key and self.api_key.startswith("SG."))

    def send(self, message: EmailMessage) -> None:
        payload = {
            "personalizations": [{"to": [{"email": message.to}]}],
            "from": {"email": message.from_email, "name": message.from_name},
            "subject": message.subject,
            "content": [{"type": "text/html", "value": message.html}],
        }

        if message.attachment_bytes and message.attachment_filename:
            payload["attachments"] = [
                {
                    "content": base64.b64encode(message.attachment_bytes).decode(),
                    "filename": message.attachment_filename,
                    "type": "application/pdf",
                }
            ]

        resp = requests.post(
            self.API_URL,
            json=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=30,
        )

        if resp.status_code >= 400:
            raise Exception(f"SendGrid error {resp.status_code}: {resp.text}")
