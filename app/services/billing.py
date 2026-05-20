"""
Subscription tier logic and Stripe integration helpers.
"""

import uuid
from datetime import datetime

from app.database import get_session, UserRow, SubscriptionRow


# ── Tier Definitions ─────────────────────────────────────────────────

TIERS = {
    "free": {
        "name": "Free",
        "price_monthly": 0,
        "max_active_jobs": 3,
        "ai_chat_messages": 10,       # per month
        "template_access": "free",     # only free-tier templates
        "can_publish_templates": False,
        "email_support": False,
        "features": [
            "3 active jobs (delete to make room)",
            "10 AI chat messages/month",
            "Free-tier templates only",
            "Community support",
        ],
    },
    "classic": {
        "name": "Classic",
        "price_monthly": 12,
        "max_active_jobs": None,       # unlimited
        "ai_chat_messages": 100,       # per month
        "template_access": "all",
        "can_publish_templates": True,
        "email_support": True,
        "features": [
            "Unlimited jobs",
            "100 AI chat messages/month",
            "All templates",
            "Publish templates to community",
            "Email support",
        ],
    },
    "pro": {
        "name": "Pro",
        "price_monthly": 29,
        "max_active_jobs": None,       # unlimited
        "ai_chat_messages": None,      # unlimited
        "template_access": "all",
        "can_publish_templates": True,
        "email_support": True,
        "features": [
            "Unlimited jobs",
            "Unlimited AI chat",
            "All templates",
            "Publish templates to community",
            "Priority email support",
            "Early access to new features",
        ],
    },
}


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


def get_or_create_subscription(user_id: str, stripe_customer_id: str) -> SubscriptionRow:
    """Get existing subscription or create a free one."""
    session = get_session()
    try:
        sub = session.query(SubscriptionRow).filter_by(user_id=user_id).first()
        if sub:
            return sub

        sub = SubscriptionRow(
            id=str(uuid.uuid4()),
            user_id=user_id,
            stripe_customer_id=stripe_customer_id,
            tier="free",
            status="active",
        )
        session.add(sub)
        session.commit()
        session.refresh(sub)
        return sub
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
