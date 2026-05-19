import resend

from app.services.email_providers.base import EmailProvider, EmailMessage


class ResendProvider(EmailProvider):
    name = "resend"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def validate_config(self) -> bool:
        return bool(self.api_key and self.api_key.startswith("re_"))

    def send(self, message: EmailMessage) -> None:
        resend.api_key = self.api_key

        payload = {
            "from": f"{message.from_name} <{message.from_email}>",
            "to": [message.to],
            "subject": message.subject,
            "html": message.html,
        }

        if message.attachment_bytes and message.attachment_filename:
            payload["attachments"] = [
                {
                    "filename": message.attachment_filename,
                    "content": list(message.attachment_bytes),
                }
            ]

        resend.Emails.send(payload)
