"""
SQLite database for user auth, email settings, subscriptions, and templates.
Postgres-ready — swap the URL when deploying.
"""

import os
from datetime import datetime

from sqlalchemy import (
    create_engine, Column, String, Boolean, DateTime, Text,
    ForeignKey, Integer, Enum as SAEnum,
)
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
    tier = Column(String, nullable=False, default="free")  # "free", "classic", "pro"
    region = Column(String, nullable=True)  # ISO country code: "NG", "US", etc.
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class EmailSettingsRow(Base):
    __tablename__ = "email_settings"

    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    provider_name = Column(String, nullable=False)  # "resend", "sendgrid", "gmail", "smtp", etc.
    credentials_encrypted = Column(Text, nullable=False)  # Fernet-encrypted JSON
    from_name = Column(String, nullable=False, default="")
    from_email = Column(String, nullable=False, default="")
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class SubscriptionRow(Base):
    __tablename__ = "subscriptions"

    id = Column(String, primary_key=True)  # UUID
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    payment_provider = Column(String, nullable=False, default="stripe")  # "stripe" or "paystack"
    stripe_customer_id = Column(String, nullable=True, index=True)
    stripe_subscription_id = Column(String, nullable=True, unique=True)
    paystack_customer_code = Column(String, nullable=True)
    paystack_subscription_code = Column(String, nullable=True)
    tier = Column(String, nullable=False, default="free")  # "free", "classic", "pro"
    status = Column(String, nullable=False, default="active")  # "active", "cancelled", "past_due", "trialing"
    current_period_start = Column(DateTime, nullable=True)
    current_period_end = Column(DateTime, nullable=True)
    cancel_at_period_end = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class AIUsageRow(Base):
    __tablename__ = "ai_usage"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    year_month = Column(String, nullable=False, index=True)  # e.g. "2026-05"
    count = Column(Integer, nullable=False, default=0)


class TemplateRow(Base):
    __tablename__ = "templates"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False, default="Untitled")
    description = Column(String, nullable=False, default="")
    owner_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)  # null = system template
    owner_name = Column(String, nullable=False, default="VolleyPacket")  # display name
    visibility = Column(String, nullable=False, default="private")  # "private" or "public"
    tier_required = Column(String, nullable=False, default="free")  # "free", "classic", "pro"
    config_json = Column(Text, nullable=False)  # full template JSON
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
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
