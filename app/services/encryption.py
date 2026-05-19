"""
Fernet symmetric encryption for stored credentials.
Encrypts API keys and SMTP passwords at rest in the database.
"""

import json
from cryptography.fernet import Fernet

from app import config


def _get_fernet() -> Fernet:
    key = config.ENCRYPTION_KEY
    if not key:
        raise RuntimeError(
            "ENCRYPTION_KEY not set. Generate one with: "
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(key.encode())


def encrypt_credentials(credentials: dict) -> str:
    """Encrypt a credentials dict to a Fernet token string."""
    f = _get_fernet()
    payload = json.dumps(credentials).encode()
    return f.encrypt(payload).decode()


def decrypt_credentials(encrypted: str) -> dict:
    """Decrypt a Fernet token string back to a credentials dict."""
    f = _get_fernet()
    payload = f.decrypt(encrypted.encode())
    return json.loads(payload.decode())
