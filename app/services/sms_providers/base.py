from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SmsMessage:
    """Provider-agnostic SMS payload."""
    to: str          # canonical E.164, e.g. "+2348012345678"
    body: str        # plain text
    sender_id: str   # alphanumeric sender ID or sending number


class SmsProvider(ABC):
    """Base class for all SMS providers (mirrors EmailProvider)."""

    name: str = "base"

    @abstractmethod
    def send(self, message: SmsMessage) -> None:
        """Send a single SMS. Raises on failure."""
        ...

    @abstractmethod
    def validate_config(self) -> bool:
        """Return True if the provider config is valid and ready to send."""
        ...
