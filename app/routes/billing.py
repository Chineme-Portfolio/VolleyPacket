"""
Dual billing routes: Stripe (international) + Paystack (Nigeria).
Provider is chosen based on user's region.
"""

import uuid
import logging
from datetime import datetime

import stripe
from fastapi import APIRouter, HTTPException, Depends, Request, Query, status
from pydantic import BaseModel

from app import config
from app.database import get_session, UserRow, SubscriptionRow
from app.dependencies import get_current_user
from app.services.billing import (
    TIERS, get_user_tier, get_tier_limits, update_user_tier,
    get_currency_for_region, get_provider_for_region,
    get_user_region, set_user_region,
)
from app.services import paystack as ps

router = APIRouter()
logger = logging.getLogger(__name__)

stripe.api_key = config.STRIPE_SECRET_KEY


# ── Request / Response Models ─────────────────────────────────────────


class CheckoutRequest(BaseModel):
    tier: str  # "classic" or "pro"


class SubscriptionResponse(BaseModel):
    tier: str
    status: str
    cancel_at_period_end: bool
    current_period_end: str | None
    payment_provider: str | None
    stripe_customer_id: str | None


# ── Stripe Helpers ───────────────────────────────────────────────────


def _get_stripe_price_id(tier: str) -> str:
    if tier == "classic":
        return config.STRIPE_PRICE_CLASSIC
    elif tier == "pro":
        return config.STRIPE_PRICE_PRO
    raise ValueError(f"No Stripe price for tier: {tier}")


def _get_or_create_stripe_customer(user: UserRow) -> str:
    session = get_session()
    try:
        sub = session.query(SubscriptionRow).filter_by(user_id=user.id).first()
        stored_id = sub.stripe_customer_id if sub else None
    finally:
        session.close()

    # Verify the stored customer still exists in the current Stripe account.
    # IDs created in test mode (or a different account) are stale once live
    # keys are in use — clear them and create a fresh customer instead.
    if stored_id:
        try:
            customer = stripe.Customer.retrieve(stored_id)
            if not getattr(customer, "deleted", False):
                return stored_id
        except stripe.InvalidRequestError:
            logger.warning(
                f"Stale Stripe customer {stored_id} for user {user.id} — creating a new one"
            )

    customer = stripe.Customer.create(
        email=user.email,
        metadata={"user_id": user.id},
    )

    session = get_session()
    try:
        sub = session.query(SubscriptionRow).filter_by(user_id=user.id).first()
        if sub:
            sub.stripe_customer_id = customer.id
        else:
            sub = SubscriptionRow(
                id=str(uuid.uuid4()),
                user_id=user.id,
                payment_provider="stripe",
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


# ── Routes ───────────────────────────────────────────────────────────


@router.get("/tiers")
def list_tiers(region: str = Query(None)):
    """List tiers with pricing for the given region's currency."""
    currency = get_currency_for_region(region)

    result = {}
    for key, t in TIERS.items():
        pricing = t["pricing"][currency]
        result[key] = {
            "name": t["name"],
            "price_monthly": pricing["price_monthly"],
            "currency": currency,
            "currency_symbol": pricing["currency_symbol"],
            "features": t["features"],
            "max_active_jobs": t["max_active_jobs"],
            "ai_chat_messages": t["ai_chat_messages"],
            "can_publish_templates": t["can_publish_templates"],
        }
    return result


def _detect_country_from_ip(ip: str) -> str | None:
    """Look up country code from IP using free ip-api.com (no key needed, 45 req/min)."""
    import requests as req
    try:
        resp = req.get(f"http://ip-api.com/json/{ip}?fields=countryCode", timeout=3)
        if resp.status_code == 200:
            code = resp.json().get("countryCode", "").upper()
            if code and len(code) == 2:
                return code
    except Exception:
        pass
    return None


@router.get("/region")
def get_region(user: UserRow = Depends(get_current_user), request: Request = None):
    """
    Get the user's region. If not set yet, auto-detect from IP and lock it in.
    Region is immutable once set — prevents currency gaming.
    """
    region = get_user_region(user.id)
    if region:
        return {"region": region, "locked": True}

    detected = "US"
    if request:
        # 1. Cloudflare / Vercel header (if behind CF proxy)
        cf_country = request.headers.get("cf-ipcountry", "").upper()
        if cf_country and cf_country != "XX":
            detected = cf_country
        else:
            # 2. GeoIP lookup from the real client IP
            client_ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
            if not client_ip:
                client_ip = request.client.host if request.client else ""
            if client_ip:
                geo_country = _detect_country_from_ip(client_ip)
                if geo_country:
                    detected = geo_country
                    logger.info("Region auto-detected from IP %s → %s", client_ip, detected)

            # 3. Fallback: Accept-Language hints for Nigerian languages
            if detected == "US":
                accept_lang = request.headers.get("accept-language", "").lower()
                if any(hint in accept_lang for hint in ["ng", "ha", "ig", "yo", "pcm"]):
                    detected = "NG"

    set_user_region(user.id, detected)
    logger.info("Region locked for user %s → %s", user.id, detected)
    return {"region": detected, "locked": True}


@router.post("/region/reset")
def reset_region(user: UserRow = Depends(get_current_user), request: Request = None):
    """
    Re-detect region from the current IP. Useful when a user's region
    was incorrectly detected (e.g. before GeoIP was implemented).
    Only works if the user has no active paid subscription.
    """
    # Don't allow reset if they have an active paid subscription
    session = get_session()
    try:
        sub = session.query(SubscriptionRow).filter_by(user_id=user.id).first()
        if sub and sub.tier not in ("free", None) and sub.status == "active":
            raise HTTPException(
                status_code=400,
                detail="Cannot reset region with an active subscription. Contact support.",
            )
    finally:
        session.close()

    # Clear existing region so get_region re-detects
    set_user_region(user.id, "")
    session = get_session()
    try:
        u = session.get(UserRow, user.id)
        if u:
            u.region = None
            session.commit()
    finally:
        session.close()

    # Re-detect
    return get_region(user=user, request=request)


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
            payment_provider=None,
            stripe_customer_id=None,
        )

    return SubscriptionResponse(
        tier=tier,
        status=sub.status,
        cancel_at_period_end=sub.cancel_at_period_end,
        current_period_end=sub.current_period_end.isoformat() if sub.current_period_end else None,
        payment_provider=getattr(sub, "payment_provider", "stripe"),
        stripe_customer_id=sub.stripe_customer_id,
    )


@router.post("/checkout")
def create_checkout_session(req: CheckoutRequest, user: UserRow = Depends(get_current_user)):
    """Create a checkout session via Stripe or Paystack based on user's locked region."""
    if req.tier not in ("classic", "pro"):
        raise HTTPException(status_code=400, detail="Tier must be 'classic' or 'pro'")

    region = get_user_region(user.id)
    provider = get_provider_for_region(region)

    if provider == "paystack":
        return _checkout_paystack(user, req.tier)
    else:
        return _checkout_stripe(user, req.tier)


def _checkout_stripe(user: UserRow, tier: str) -> dict:
    if not config.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe is not configured")

    try:
        price_id = _get_stripe_price_id(tier)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not price_id:
        raise HTTPException(status_code=503, detail=f"Stripe price ID not configured for {tier}")

    customer_id = _get_or_create_stripe_customer(user)

    try:
        checkout_session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url=f"{config.FRONTEND_URL}/settings/billing?success=true",
            cancel_url=f"{config.FRONTEND_URL}/settings/billing?cancelled=true",
            metadata={"user_id": user.id, "tier": tier},
        )
    except stripe.StripeError as e:
        raise HTTPException(status_code=502, detail=f"Stripe error: {str(e)}")

    return {"checkout_url": checkout_session.url}


def _checkout_paystack(user: UserRow, tier: str) -> dict:
    if not config.PAYSTACK_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Paystack is not configured")

    try:
        plan_code = ps.get_paystack_plan_code(tier)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not plan_code:
        raise HTTPException(status_code=503, detail=f"Paystack plan not configured for {tier}")

    pricing = TIERS[tier]["pricing"]["NGN"]
    amount_kobo = pricing["price_monthly"] * 100

    try:
        result = ps.initialize_transaction(
            email=user.email,
            amount_kobo=amount_kobo,
            plan_code=plan_code,
            metadata={"user_id": user.id, "tier": tier},
            callback_url=f"{config.FRONTEND_URL}/settings/billing?success=true",
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Paystack error: {str(e)}")

    return {"checkout_url": result["authorization_url"]}


@router.post("/portal")
def create_portal_session(user: UserRow = Depends(get_current_user)):
    """Create a billing management session (Stripe portal or Paystack manage link)."""
    session = get_session()
    try:
        sub = session.query(SubscriptionRow).filter_by(user_id=user.id).first()
    finally:
        session.close()

    if not sub:
        raise HTTPException(status_code=400, detail="No billing account found. Subscribe to a plan first.")

    provider = getattr(sub, "payment_provider", "stripe")

    if provider == "paystack":
        sub_code = getattr(sub, "paystack_subscription_code", None)
        if not sub_code:
            raise HTTPException(status_code=400, detail="No Paystack subscription found.")
        manage_url = ps.get_manage_subscription_link(sub_code)
        return {"portal_url": manage_url}
    else:
        if not config.STRIPE_SECRET_KEY:
            raise HTTPException(status_code=503, detail="Stripe is not configured")

        # Validates the stored customer ID and recreates it if stale
        customer_id = _get_or_create_stripe_customer(user)

        try:
            portal_session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=f"{config.FRONTEND_URL}/settings/billing",
            )
        except stripe.StripeError as e:
            raise HTTPException(status_code=502, detail=f"Stripe error: {str(e)}")

        return {"portal_url": portal_session.url}


# ── Stripe Webhook ───────────────────────────────────────────────────


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
    except stripe.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_type = event["type"]
    data = event["data"]["object"]
    logger.info(f"Stripe webhook received: {event_type} ({event.get('id')})")

    try:
        if event_type == "checkout.session.completed":
            _handle_stripe_checkout(data)
        elif event_type == "customer.subscription.updated":
            _handle_stripe_subscription_updated(data)
        elif event_type == "customer.subscription.deleted":
            _handle_stripe_subscription_deleted(data)
        elif event_type == "invoice.payment_failed":
            _handle_stripe_payment_failed(data)
    except Exception:
        # logger.exception includes the full traceback
        logger.exception(f"Stripe webhook handler error for {event_type}")
        # Return 200 anyway so Stripe doesn't keep retrying

    return {"received": True}


def _handle_stripe_checkout(session_data: dict):
    metadata = session_data.get("metadata") or {}
    user_id = metadata.get("user_id")
    tier = metadata.get("tier")
    subscription_id = session_data.get("subscription")
    customer_id = session_data.get("customer")

    if not user_id or not tier:
        logger.warning(
            f"checkout.session.completed missing metadata "
            f"(user_id={user_id!r}, tier={tier!r}, session={session_data.get('id')!r}) — skipping"
        )
        return

    logger.info(f"Upgrading user {user_id} to {tier} (sub={subscription_id})")
    update_user_tier(user_id, tier)

    db_session = get_session()
    try:
        sub = db_session.query(SubscriptionRow).filter_by(user_id=user_id).first()
        if sub:
            sub.tier = tier
            sub.status = "active"
            sub.payment_provider = "stripe"
            sub.stripe_subscription_id = subscription_id
            sub.stripe_customer_id = customer_id
            sub.updated_at = datetime.utcnow()
        else:
            sub = SubscriptionRow(
                id=str(uuid.uuid4()),
                user_id=user_id,
                payment_provider="stripe",
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


def _handle_stripe_subscription_updated(sub_data: dict):
    stripe_sub_id = sub_data.get("id")
    sub_status = sub_data.get("status")
    cancel_at_period_end = sub_data.get("cancel_at_period_end", False)

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
            sub.status = sub_status
            sub.cancel_at_period_end = cancel_at_period_end
            if period_start:
                sub.current_period_start = datetime.utcfromtimestamp(period_start)
            if period_end:
                sub.current_period_end = datetime.utcfromtimestamp(period_end)
            sub.updated_at = datetime.utcnow()
            update_user_tier(sub.user_id, tier if sub_status == "active" else "free")
            db_session.commit()
    except Exception:
        db_session.rollback()
        raise
    finally:
        db_session.close()


def _handle_stripe_subscription_deleted(sub_data: dict):
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


def _handle_stripe_payment_failed(invoice_data: dict):
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


# ── Paystack Webhook ─────────────────────────────────────────────────


@router.post("/webhook/paystack")
async def paystack_webhook(request: Request):
    """Handle Paystack webhook events."""
    payload = await request.body()
    signature = request.headers.get("x-paystack-signature", "")

    if not ps.verify_webhook_signature(payload, signature):
        raise HTTPException(status_code=400, detail="Invalid signature")

    import json
    try:
        event = json.loads(payload)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid payload")

    event_type = event.get("event", "")
    data = event.get("data", {})

    try:
        if event_type == "charge.success":
            _handle_paystack_charge_success(data)
        elif event_type == "subscription.create":
            _handle_paystack_subscription_create(data)
        elif event_type in ("subscription.disable", "subscription.not_renew"):
            _handle_paystack_subscription_cancelled(data)
        elif event_type == "invoice.payment_failed":
            _handle_paystack_payment_failed(data)
    except Exception as e:
        logger.error(f"Paystack webhook handler error: {e}")

    return {"received": True}


def _handle_paystack_charge_success(data: dict):
    """Handle successful charge — subscription is auto-created by Paystack when plan is attached."""
    metadata = data.get("metadata", {})
    user_id = metadata.get("user_id")
    tier = metadata.get("tier")
    customer = data.get("customer", {})
    customer_code = customer.get("customer_code", "")

    if not user_id or not tier:
        return

    update_user_tier(user_id, tier)

    db_session = get_session()
    try:
        sub = db_session.query(SubscriptionRow).filter_by(user_id=user_id).first()
        if sub:
            sub.tier = tier
            sub.status = "active"
            sub.payment_provider = "paystack"
            sub.paystack_customer_code = customer_code
            sub.updated_at = datetime.utcnow()
        else:
            sub = SubscriptionRow(
                id=str(uuid.uuid4()),
                user_id=user_id,
                payment_provider="paystack",
                paystack_customer_code=customer_code,
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


def _handle_paystack_subscription_create(data: dict):
    """Handle subscription creation — update the subscription code."""
    subscription_code = data.get("subscription_code", "")
    customer = data.get("customer", {})
    customer_code = customer.get("customer_code", "")
    email_token = data.get("email_token", "")

    plan = data.get("plan", {})
    plan_code = plan.get("plan_code", "")

    tier = "free"
    if plan_code == config.PAYSTACK_PLAN_CLASSIC:
        tier = "classic"
    elif plan_code == config.PAYSTACK_PLAN_PRO:
        tier = "pro"

    db_session = get_session()
    try:
        sub = db_session.query(SubscriptionRow).filter_by(paystack_customer_code=customer_code).first()
        if sub:
            sub.paystack_subscription_code = subscription_code
            sub.tier = tier
            sub.status = "active"
            sub.updated_at = datetime.utcnow()
            update_user_tier(sub.user_id, tier)
            db_session.commit()
    except Exception:
        db_session.rollback()
        raise
    finally:
        db_session.close()


def _handle_paystack_subscription_cancelled(data: dict):
    """Handle subscription cancellation/disable."""
    subscription_code = data.get("subscription_code", "")

    db_session = get_session()
    try:
        sub = db_session.query(SubscriptionRow).filter_by(paystack_subscription_code=subscription_code).first()
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


def _handle_paystack_payment_failed(data: dict):
    """Handle failed payment."""
    subscription = data.get("subscription", {})
    subscription_code = subscription.get("subscription_code", "")

    db_session = get_session()
    try:
        sub = db_session.query(SubscriptionRow).filter_by(paystack_subscription_code=subscription_code).first()
        if sub:
            sub.status = "past_due"
            sub.updated_at = datetime.utcnow()
            db_session.commit()
    except Exception:
        db_session.rollback()
        raise
    finally:
        db_session.close()
