"""
Subscription tier logic with dual-currency pricing (USD/NGN).
"""

import uuid
from datetime import datetime

from app.database import get_session, UserRow, SubscriptionRow, AIUsageRow


# ── Tier Definitions ─────────────────────────────────────────────────

TIERS = {
    "free": {
        "name": "Free",
        "pricing": {
            "USD": {"price_monthly": 0, "currency_symbol": "$"},
            "NGN": {"price_monthly": 0, "currency_symbol": "₦"},
        },
        "max_active_jobs": 3,
        "max_rows": 5000,               # No image links
        "max_rows_with_images": 3000,    # Has image/photo links
        "ai_chat_messages": 10,
        "template_access": "free",
        "can_publish_templates": False,
        "email_support": False,
        "features": [
            "3 active jobs",
            "Up to 5,000 recipients per job",
            "10 AI chat messages/month",
            "Free-tier templates only",
            "Community support",
        ],
    },
    "classic": {
        "name": "Classic",
        "pricing": {
            "USD": {"price_monthly": 12, "currency_symbol": "$"},
            "NGN": {"price_monthly": 8500, "currency_symbol": "₦"},
        },
        "max_active_jobs": None,
        "max_rows": 10000,              # No image links
        "max_rows_with_images": 7000,   # Has image/photo links
        "ai_chat_messages": 100,
        "template_access": "all",
        "can_publish_templates": True,
        "email_support": True,
        "features": [
            "Unlimited jobs",
            "Up to 10,000 recipients per job",
            "100 AI chat messages/month",
            "All templates",
            "Publish templates to community",
            "Email support",
        ],
    },
    "pro": {
        "name": "Pro",
        "pricing": {
            "USD": {"price_monthly": 29, "currency_symbol": "$"},
            "NGN": {"price_monthly": 23500, "currency_symbol": "₦"},
        },
        "max_active_jobs": None,
        "max_rows": None,               # Unlimited
        "max_rows_with_images": None,   # Unlimited
        "ai_chat_messages": None,
        "template_access": "all",
        "can_publish_templates": True,
        "email_support": True,
        "features": [
            "Unlimited jobs",
            "Unlimited recipients per job",
            "Unlimited AI chat",
            "All templates",
            "Publish templates to community",
            "Priority email support",
            "Early access to new features",
        ],
    },
}


# ── Region / Currency Helpers ────────────────────────────────────────


def get_currency_for_region(region: str | None) -> str:
    """Map region to currency. Nigeria -> NGN, everything else -> USD."""
    return "NGN" if region and region.upper() == "NG" else "USD"


def get_provider_for_region(region: str | None) -> str:
    """Map region to payment provider. Nigeria -> paystack, else -> stripe."""
    return "paystack" if region and region.upper() == "NG" else "stripe"


def get_user_region(user_id: str) -> str | None:
    """Get the user's stored region."""
    session = get_session()
    try:
        user = session.get(UserRow, user_id)
        return getattr(user, "region", None) if user else None
    finally:
        session.close()


def set_user_region(user_id: str, region: str):
    """Store the user's region."""
    session = get_session()
    try:
        user = session.get(UserRow, user_id)
        if user:
            user.region = region.upper()
            session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ── Tier Logic ───────────────────────────────────────────────────────


def get_user_tier(user_id: str) -> str:
    """Get the effective tier for a user."""
    session = get_session()
    try:
        user = session.get(UserRow, user_id)
        if not user:
            return "free"
        return user.tier or "free"
    finally:
        session.close()


def get_tier_limits(tier: str) -> dict:
    """Return the limits dict for a tier."""
    return TIERS.get(tier, TIERS["free"])


def check_job_limit(user_id: str, current_job_count: int) -> bool:
    """Return True if the user can create another job."""
    tier = get_user_tier(user_id)
    limits = get_tier_limits(tier)
    max_jobs = limits["max_active_jobs"]
    if max_jobs is None:
        return True
    return current_job_count < max_jobs


def check_row_limit(user_id: str, row_count: int, columns: list[str]) -> tuple[bool, int | None]:
    """
    Check if the uploaded data is within the user's tier row limit.
    Returns (allowed, max_rows).
    max_rows=None means unlimited.

    Image link detection: if any column looks like it holds photo/image URLs,
    we use the stricter max_rows_with_images limit (more compute for downloads + storage).
    """
    tier = get_user_tier(user_id)
    limits = get_tier_limits(tier)

    # Detect columns that likely contain image/photo links
    image_col_patterns = {"photo", "image", "picture", "headshot", "avatar", "logo"}
    has_image_links = any(
        any(pattern in col.lower() for pattern in image_col_patterns)
        for col in columns
    )

    if has_image_links:
        max_rows = limits.get("max_rows_with_images")
    else:
        max_rows = limits.get("max_rows")

    if max_rows is None:
        return True, None

    return row_count <= max_rows, max_rows


def check_template_access(user_tier: str, template_tier_required: str) -> bool:
    """Return True if the user's tier grants access to this template."""
    tier_rank = {"free": 0, "classic": 1, "pro": 2}
    return tier_rank.get(user_tier, 0) >= tier_rank.get(template_tier_required, 0)


def update_user_tier(user_id: str, new_tier: str):
    """Update the user's tier in the users table."""
    session = get_session()
    try:
        user = session.get(UserRow, user_id)
        if user:
            user.tier = new_tier
            session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ── AI Usage Tracking ───────────────────────────────────────────────


def _current_month() -> str:
    """Return current year-month string like '2026-05'."""
    return datetime.utcnow().strftime("%Y-%m")


def get_ai_usage(user_id: str) -> int:
    """Get the AI message count for the current month."""
    session = get_session()
    try:
        month = _current_month()
        row = session.query(AIUsageRow).filter_by(
            user_id=user_id, year_month=month
        ).first()
        return row.count if row else 0
    finally:
        session.close()


def check_ai_limit(user_id: str) -> tuple[bool, int, int | None]:
    """
    Check if the user can make another AI call.
    Returns (allowed, current_count, limit).
    limit=None means unlimited.
    """
    tier = get_user_tier(user_id)
    limits = get_tier_limits(tier)
    max_messages = limits["ai_chat_messages"]
    current = get_ai_usage(user_id)

    if max_messages is None:
        return True, current, None

    return current < max_messages, current, max_messages


def increment_ai_usage(user_id: str):
    """Increment the AI message counter for the current month."""
    session = get_session()
    try:
        month = _current_month()
        row = session.query(AIUsageRow).filter_by(
            user_id=user_id, year_month=month
        ).first()
        if row:
            row.count += 1
        else:
            row = AIUsageRow(
                id=str(uuid.uuid4()),
                user_id=user_id,
                year_month=month,
                count=1,
            )
            session.add(row)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
