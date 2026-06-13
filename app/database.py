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


class JobRow(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True)  # job_id (8-char UUID)
    owner_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String, nullable=False, default="created")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    timestamp = Column(String, nullable=False)  # "YYYYMMDD_HHMMSS" for file naming

    candidate_file = Column(String, nullable=False)  # original upload filename
    candidate_count = Column(Integer, nullable=False, default=0)
    columns_json = Column(Text, nullable=False, default="[]")  # JSON array of column names

    template_id = Column(String, nullable=True)  # FK to the ORIGIN library template (for reset/display)
    template_json = Column(Text, nullable=True)  # job-local fork of TemplateConfig — edits live here, never on TemplateRow
    job_mode = Column(String, nullable=False, default="dynamic_pdf")
    email_subject = Column(String, nullable=False, default="")
    email_body = Column(Text, nullable=False, default="")
    sms_body = Column(Text, nullable=False, default="")

    cancelled = Column(Boolean, nullable=False, default=False)
    column_mapping_confirmed = Column(Boolean, nullable=False, default=False)
    paused_json = Column(Text, nullable=False, default='{"pdfs":false,"emails":false,"sms":false,"photos":false}')
    stop_flags_json = Column(Text, nullable=False, default='{"pdfs":false,"emails":false,"sms":false,"photos":false}')
    tasks_json = Column(Text, nullable=False, default='{}')  # JSON of TaskStatus dicts

    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


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

    # Auto-migrate: add missing columns to ALL existing tables (non-destructive, never drops data)
    _auto_migrate(_engine)

    Base.metadata.create_all(_engine)

    # Mark any tasks stuck as "running" from a previous process as "interrupted"
    from app.services.jobs import mark_stale_running_tasks
    mark_stale_running_tasks()


def _auto_migrate(engine):
    """Add missing columns to existing tables by reading SQLAlchemy model definitions.

    Runs on every startup. Only adds columns — never drops tables or columns.
    Works with both PostgreSQL and SQLite.
    """
    import logging
    from sqlalchemy import inspect, text

    log = logging.getLogger(__name__)
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue  # Table doesn't exist yet — create_all() will handle it

        existing_cols = {c["name"] for c in inspector.get_columns(table.name)}
        model_cols = {c.name: c for c in table.columns}
        missing = set(model_cols.keys()) - existing_cols

        if not missing:
            continue

        log.info(f"Auto-migrate: {table.name} missing columns {missing}")

        with engine.begin() as conn:
            for col_name in missing:
                col = model_cols[col_name]
                try:
                    col_type = col.type.compile(dialect=engine.dialect)

                    # Build the default clause
                    default_sql = ""
                    if col.default is not None and col.default.arg is not None:
                        default_val = col.default.arg
                        if isinstance(default_val, bool):
                            default_sql = f" DEFAULT {1 if default_val else 0}"
                        elif isinstance(default_val, (int, float)):
                            default_sql = f" DEFAULT {default_val}"
                        elif isinstance(default_val, str):
                            escaped = default_val.replace("'", "''")
                            default_sql = f" DEFAULT '{escaped}'"
                        # Skip callable defaults (like datetime.utcnow) — they can't be expressed in DDL

                    nullable = " NOT NULL" if not col.nullable else ""

                    # If NOT NULL and no default, we must provide one to avoid crashing on existing rows
                    if not col.nullable and not default_sql:
                        type_str = str(col_type).upper()
                        if "INT" in type_str:
                            default_sql = " DEFAULT 0"
                        elif "BOOL" in type_str:
                            default_sql = " DEFAULT 0"
                        elif "TEXT" in type_str or "VARCHAR" in type_str or "CHAR" in type_str:
                            default_sql = " DEFAULT ''"
                        else:
                            # Can't infer a safe default — make it nullable to avoid crash
                            nullable = ""

                    sql = f"ALTER TABLE {table.name} ADD COLUMN {col_name} {col_type}{nullable}{default_sql}"
                    log.info(f"Auto-migrate: {sql}")
                    conn.execute(text(sql))
                    log.info(f"Auto-migrate: added {table.name}.{col_name}")
                except Exception as e:
                    # "already exists" is fine (race between workers), anything else is a real problem
                    err_msg = str(e).lower()
                    if "already exists" in err_msg or "duplicate column" in err_msg:
                        pass
                    else:
                        log.error(f"Auto-migrate: failed to add {table.name}.{col_name}: {e}")


def get_session() -> Session:
    if _SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _SessionLocal()
