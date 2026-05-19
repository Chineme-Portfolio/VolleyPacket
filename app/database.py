"""
SQLite database for user auth and email settings.
Postgres-ready — swap the URL when deploying.
"""

import os
from datetime import datetime

from sqlalchemy import create_engine, Column, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from app import config

Base = declarative_base()


# ── Tables ────────────────────────────────────────────────────────────


class UserRow(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=True)  # null for Google OAuth users
    auth_provider = Column(String, nullable=False, default="local")  # "local" or "google"
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class EmailSettingsRow(Base):
    __tablename__ = "email_settings"

    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    provider_name = Column(String, nullable=False)  # "resend", "sendgrid", "gmail", "smtp", etc.
    credentials_encrypted = Column(Text, nullable=False)  # Fernet-encrypted JSON
    from_name = Column(String, nullable=False, default="")
    from_email = Column(String, nullable=False, default="")
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


# ── Engine & Session ──────────────────────────────────────────────────

_engine = None
_SessionLocal = None


def init_db():
    global _engine, _SessionLocal

    db_url = os.getenv("DATABASE_URL")

    if db_url:
        # Production: PostgreSQL
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
    else:
        # Local: SQLite
        os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
        db_url = f"sqlite:///{config.DB_PATH}"

    _engine = create_engine(db_url, pool_pre_ping=True)
    _SessionLocal = sessionmaker(bind=_engine)
    Base.metadata.create_all(_engine)


def get_session() -> Session:
    if _SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _SessionLocal()
