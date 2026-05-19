from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class EmailMessage:
    """Provider-agnostic email payload."""
    from_name: str
    from_email: str
    to: str
    subject: str
    html: str
    attachment_filename: str | None = None
    attachment_bytes: bytes | None = None


class EmailProvider(ABC):
    """Base class for all email providers."""

    name: str = "base"

    @abstractmethod
    def send(self, message: EmailMessage) -> None:
        """Send a single email. Raises on failure."""
        ...

    @abstractmethod
    def validate_config(self) -> bool:
        """Return True if the provider config is valid and ready to send."""
        ...
