"""
Paystack REST API wrapper for subscriptions and payments.
No SDK needed — plain requests calls.
"""

import hashlib
import hmac
import logging

import requests

from app import config

logger = logging.getLogger(__name__)

BASE_URL = "https://api.paystack.co"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {config.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }


def initialize_transaction(
    email: str,
    amount_kobo: int,
    plan_code: str,
    metadata: dict,
    callback_url: str,
) -> dict:
    """
    Initialize a Paystack transaction (for subscription with first charge).
    amount_kobo: amount in kobo (1 NGN = 100 kobo)
    Returns: {"authorization_url": "...", "access_code": "...", "reference": "..."}
    """
    payload = {
        "email": email,
        "amount": amount_kobo,
        "plan": plan_code,
        "callback_url": callback_url,
        "metadata": metadata,
    }
    resp = requests.post(f"{BASE_URL}/transaction/initialize", json=payload, headers=_headers(), timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("status"):
        raise ValueError(data.get("message", "Paystack initialization failed"))
    return data["data"]


def verify_transaction(reference: str) -> dict:
    """
    Verify a Paystack transaction by reference.
    Returns the full transaction data.
    """
    resp = requests.get(f"{BASE_URL}/transaction/verify/{reference}", headers=_headers(), timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("status"):
        raise ValueError(data.get("message", "Transaction verification failed"))
    return data["data"]


def get_subscription(subscription_code: str) -> dict:
    """Fetch subscription details."""
    resp = requests.get(f"{BASE_URL}/subscription/{subscription_code}", headers=_headers(), timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return data.get("data", {})


def disable_subscription(subscription_code: str, email_token: str) -> bool:
    """Disable (cancel) a subscription."""
    payload = {"code": subscription_code, "token": email_token}
    resp = requests.post(f"{BASE_URL}/subscription/disable", json=payload, headers=_headers(), timeout=15)
    return resp.status_code == 200


def get_manage_subscription_link(subscription_code: str) -> str:
    """
    Get the Paystack subscription management link.
    Paystack provides a manage_link in subscription data.
    """
    try:
        sub = get_subscription(subscription_code)
        # Paystack returns a manage link if subscription is active
        return sub.get("manage_link", "") or sub.get("manage_url", "") or f"https://paystack.com/pay/manage/{subscription_code}"
    except Exception:
        return f"https://paystack.com/pay/manage/{subscription_code}"


def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """
    Verify Paystack webhook signature using HMAC SHA-512.
    """
    if not config.PAYSTACK_WEBHOOK_SECRET:
        return False
    expected = hmac.new(
        config.PAYSTACK_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha512,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def get_paystack_plan_code(tier: str) -> str:
    """Map tier to Paystack plan code."""
    if tier == "classic":
        return config.PAYSTACK_PLAN_CLASSIC
    elif tier == "pro":
        return config.PAYSTACK_PLAN_PRO
    raise ValueError(f"No Paystack plan for tier: {tier}")
