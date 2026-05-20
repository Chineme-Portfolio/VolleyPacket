"""
Stripe billing routes: checkout, portal, webhooks, subscription status.
"""

import uuid
from datetime import datetime

import stripe
from fastapi import APIRouter, HTTPException, Depends, Request, status
from pydantic import BaseModel

from app import config
from app.database import get_session, UserRow, SubscriptionRow
from app.dependencies import get_current_user
from app.services.billing import TIERS, get_user_tier, get_tier_limits, update_user_tier

router = APIRouter()

stripe.api_key = config.STRIPE_SECRET_KEY


# ── Request / Response Models ─────────────────────────────────────────


class CheckoutRequest(BaseModel):
    tier: str  # "classic" or "pro"


class SubscriptionResponse(BaseModel):
    tier: str
    status: str
    cancel_at_period_end: bool
    current_period_end: str | None
    stripe_customer_id: str | None


# ── Helper ────────────────────────────────────────────────────────────


def _get_stripe_price_id(tier: str) -> str:
    if tier == "classic":
        return config.STRIPE_PRICE_CLASSIC
    elif tier == "pro":
        return config.STRIPE_PRICE_PRO
    raise ValueError(f"No Stripe price for tier: {tier}")


def _get_or_create_stripe_customer(user: UserRow) -> str:
    """Get existing Stripe customer or create one. Returns customer ID."""
    session = get_session()
    try:
        sub = session.query(SubscriptionRow).filter_by(user_id=user.id).first()
        if sub and sub.stripe_customer_id:
            return sub.stripe_customer_id
    finally:
        session.close()

    # Create Stripe customer
    customer = stripe.Customer.create(
        email=user.email,
        metadata={"user_id": user.id},
    )

    # Store it
    session = get_session()
    try:
        sub = session.query(SubscriptionRow).filter_by(user_id=user.id).first()
        if sub:
            sub.stripe_customer_id = customer.id
        else:
            sub = SubscriptionRow(
                id=str(uuid.uuid4()),
                user_id=user.id,
                stripe_customer_id=customer.id,
                tier="free",
                status="active",
            )
            session.add(sub)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    return customer.id


# ── Routes ────────────────────────────────────────────────────────────


@router.get("/tiers")
def list_tiers():
    """List all available tiers and their features."""
    return {
        key: {
            "name": t["name"],
            "price_monthly": t["price_monthly"],
            "features": t["features"],
            "max_active_jobs": t["max_active_jobs"],
            "ai_chat_messages": t["ai_chat_messages"],
            "can_publish_templates": t["can_publish_templates"],
        }
        for key, t in TIERS.items()
    }


@router.get("/subscription", response_model=SubscriptionResponse)
def get_subscription(user: UserRow = Depends(get_current_user)):
    """Get the current user's subscription status."""
    session = get_session()
    try:
        sub = session.query(SubscriptionRow).filter_by(user_id=user.id).first()
    finally:
        session.close()

    tier = get_user_tier(user.id)

    if not sub:
        return SubscriptionResponse(
            tier=tier,
            status="active",
            cancel_at_period_end=False,
            current_period_end=None,
            stripe_customer_id=None,
        )

    return SubscriptionResponse(
        tier=tier,
        status=sub.status,
        cancel_at_period_end=sub.cancel_at_period_end,
        current_period_end=sub.current_period_end.isoformat() if sub.current_period_end else None,
        stripe_customer_id=sub.stripe_customer_id,
    )


@router.post("/checkout")
def create_checkout_session(req: CheckoutRequest, user: UserRow = Depends(get_current_user)):
    """Create a Stripe Checkout session for upgrading to classic or pro."""
    if req.tier not in ("classic", "pro"):
        raise HTTPException(status_code=400, detail="Tier must be 'classic' or 'pro'")

    if not config.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe is not configured")

    try:
        price_id = _get_stripe_price_id(req.tier)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not price_id:
        raise HTTPException(status_code=503, detail=f"Stripe price ID not configured for {req.tier}")

    customer_id = _get_or_create_stripe_customer(user)

    try:
        checkout_session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url=f"{config.FRONTEND_URL}/settings/billing?success=true",
            cancel_url=f"{config.FRONTEND_URL}/settings/billing?cancelled=true",
            metadata={"user_id": user.id, "tier": req.tier},
        )
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=502, detail=f"Stripe error: {str(e)}")

    return {"checkout_url": checkout_session.url}


@router.post("/portal")
def create_portal_session(user: UserRow = Depends(get_current_user)):
    """Create a Stripe Customer Portal session for managing subscription."""
    if not config.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe is not configured")

    session = get_session()
    try:
        sub = session.query(SubscriptionRow).filter_by(user_id=user.id).first()
    finally:
        session.close()

    if not sub or not sub.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No billing account found. Subscribe to a plan first.")

    try:
        portal_session = stripe.billing_portal.Session.create(
            customer=sub.stripe_customer_id,
            return_url=f"{config.FRONTEND_URL}/settings/billing",
        )
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=502, detail=f"Stripe error: {str(e)}")

    return {"portal_url": portal_session.url}


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not config.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Webhook secret not configured")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, config.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Handle the event
    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        _handle_checkout_completed(data)
    elif event_type == "customer.subscription.updated":
        _handle_subscription_updated(data)
    elif event_type == "customer.subscription.deleted":
        _handle_subscription_deleted(data)
    elif event_type == "invoice.payment_failed":
        _handle_payment_failed(data)

    return {"received": True}


# ── Webhook Handlers ──────────────────────────────────────────────────


def _handle_checkout_completed(session_data: dict):
    """Upgrade user after successful checkout."""
    user_id = session_data.get("metadata", {}).get("user_id")
    tier = session_data.get("metadata", {}).get("tier")
    subscription_id = session_data.get("subscription")
    customer_id = session_data.get("customer")

    if not user_id or not tier:
        return

    update_user_tier(user_id, tier)

    db_session = get_session()
    try:
        sub = db_session.query(SubscriptionRow).filter_by(user_id=user_id).first()
        if sub:
            sub.tier = tier
            sub.status = "active"
            sub.stripe_subscription_id = subscription_id
            sub.stripe_customer_id = customer_id
            sub.updated_at = datetime.utcnow()
        else:
            sub = SubscriptionRow(
                id=str(uuid.uuid4()),
                user_id=user_id,
                stripe_customer_id=customer_id,
                stripe_subscription_id=subscription_id,
                tier=tier,
                status="active",
            )
            db_session.add(sub)
        db_session.commit()
    except Exception:
        db_session.rollback()
        raise
    finally:
        db_session.close()


def _handle_subscription_updated(sub_data: dict):
    """Handle subscription changes (upgrade, downgrade, renewal)."""
    stripe_sub_id = sub_data.get("id")
    status = sub_data.get("status")
    cancel_at_period_end = sub_data.get("cancel_at_period_end", False)

    # Map Stripe price to tier
    items = sub_data.get("items", {}).get("data", [])
    price_id = items[0]["price"]["id"] if items else None
    tier = "free"
    if price_id == config.STRIPE_PRICE_CLASSIC:
        tier = "classic"
    elif price_id == config.STRIPE_PRICE_PRO:
        tier = "pro"

    period_start = sub_data.get("current_period_start")
    period_end = sub_data.get("current_period_end")

    db_session = get_session()
    try:
        sub = db_session.query(SubscriptionRow).filter_by(stripe_subscription_id=stripe_sub_id).first()
        if sub:
            sub.tier = tier
            sub.status = status
            sub.cancel_at_period_end = cancel_at_period_end
            if period_start:
                sub.current_period_start = datetime.utcfromtimestamp(period_start)
            if period_end:
                sub.current_period_end = datetime.utcfromtimestamp(period_end)
            sub.updated_at = datetime.utcnow()

            # Update user tier
            update_user_tier(sub.user_id, tier if status == "active" else "free")

            db_session.commit()
    except Exception:
        db_session.rollback()
        raise
    finally:
        db_session.close()


def _handle_subscription_deleted(sub_data: dict):
    """Handle subscription cancellation."""
    stripe_sub_id = sub_data.get("id")

    db_session = get_session()
    try:
        sub = db_session.query(SubscriptionRow).filter_by(stripe_subscription_id=stripe_sub_id).first()
        if sub:
            sub.status = "cancelled"
            sub.tier = "free"
            sub.updated_at = datetime.utcnow()
            update_user_tier(sub.user_id, "free")
            db_session.commit()
    except Exception:
        db_session.rollback()
        raise
    finally:
        db_session.close()


def _handle_payment_failed(invoice_data: dict):
    """Handle failed payment — mark subscription as past_due."""
    subscription_id = invoice_data.get("subscription")
    if not subscription_id:
        return

    db_session = get_session()
    try:
        sub = db_session.query(SubscriptionRow).filter_by(stripe_subscription_id=subscription_id).first()
        if sub:
            sub.status = "past_due"
            sub.updated_at = datetime.utcnow()
            db_session.commit()
    except Exception:
        db_session.rollback()
        raise
    finally:
        db_session.close()
