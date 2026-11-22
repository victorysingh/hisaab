"""Razorpay adapter (test mode): payment links and webhook signature checks.

Uses the Razorpay REST API directly with httpx, so no extra package is needed.
Keys come from environment variables (Render) or apps/api/.env (local):
  RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET, RAZORPAY_WEBHOOK_SECRET
"""

from __future__ import annotations

import hashlib
import hmac
import os
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import httpx

API = "https://api.razorpay.com/v1"
ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


@lru_cache(maxsize=1)
def _dotenv() -> dict:
    try:
        from dotenv import dotenv_values
        return {k: v for k, v in dotenv_values(ENV_FILE).items() if v}
    except Exception:
        return {}


def env(name: str) -> str:
    return (os.environ.get(name) or _dotenv().get(name) or "").strip()


def is_configured() -> bool:
    return bool(env("RAZORPAY_KEY_ID") and env("RAZORPAY_KEY_SECRET"))


class RazorpayError(RuntimeError):
    pass


def _auth() -> tuple[str, str]:
    if not is_configured():
        raise RazorpayError("Razorpay keys are not set")
    return env("RAZORPAY_KEY_ID"), env("RAZORPAY_KEY_SECRET")


def to_paise(amount) -> int:
    return int((Decimal(str(amount)) * 100).quantize(Decimal("1")))


def create_payment_link(*, invoice_id: str, amount, description: str, customer_name: str,
                        phone: str | None, http: httpx.Client | None = None) -> dict:
    """Create a Razorpay payment link. reference_id is the invoice id (must be unique per link)."""
    contact = "".join(ch for ch in (phone or "") if ch.isdigit())
    body = {
        "amount": to_paise(amount),
        "currency": "INR",
        "accept_partial": False,
        "description": description[:2048],
        "reference_id": invoice_id[:40],
        "customer": {"name": customer_name[:50], **({"contact": f"+{contact}"} if contact else {})},
        "notify": {"sms": False, "email": False},
        "reminder_enable": False,
        "notes": {"invoice_id": invoice_id, "app": "hisaab"},
    }
    client = http or httpx.Client(timeout=15)
    try:
        res = client.post(f"{API}/payment_links", json=body, auth=_auth())
    finally:
        if http is None:
            client.close()
    if res.status_code >= 400:
        try:
            detail = res.json().get("error", {}).get("description") or res.text
        except Exception:
            detail = res.text
        raise RazorpayError(f"Razorpay error {res.status_code}: {detail}")
    data = res.json()
    return {"id": data["id"], "short_url": data["short_url"], "status": data.get("status")}


def fetch_payment_link(link_id: str, http: httpx.Client | None = None) -> dict:
    client = http or httpx.Client(timeout=15)
    try:
        res = client.get(f"{API}/payment_links/{link_id}", auth=_auth())
    finally:
        if http is None:
            client.close()
    if res.status_code >= 400:
        raise RazorpayError(f"Razorpay error {res.status_code}")
    return res.json()


def verify_webhook(body: bytes, signature: str | None, secret: str | None = None) -> bool:
    secret = secret if secret is not None else env("RAZORPAY_WEBHOOK_SECRET")
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
