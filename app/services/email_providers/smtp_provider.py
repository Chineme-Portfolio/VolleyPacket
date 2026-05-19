import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

from app.services.email_providers.base import EmailProvider, EmailMessage


class SMTPProvider(EmailProvider):
    """Generic SMTP provider — works with Gmail, Zoho, Outlook, or any SMTP server."""

    name = "smtp"

    def __init__(self, host: str, port: int, username: str, password: str, use_tls: bool = True):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls

    def validate_config(self) -> bool:
        return bool(self.host and self.port and self.username and self.password)

    def send(self, message: EmailMessage) -> None:
        msg = MIMEMultipart()
        msg["From"] = f"{message.from_name} <{message.from_email}>"
        msg["To"] = message.to
        msg["Subject"] = message.subject
        msg.attach(MIMEText(message.html, "html"))

        if message.attachment_bytes and message.attachment_filename:
            part = MIMEBase("application", "pdf")
            part.set_payload(message.attachment_bytes)
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f'attachment; filename="{message.attachment_filename}"',
            )
            msg.attach(part)

        with smtplib.SMTP(self.host, self.port, timeout=30) as server:
            if self.use_tls:
                server.starttls()
            server.login(self.username, self.password)
            server.send_message(msg)
