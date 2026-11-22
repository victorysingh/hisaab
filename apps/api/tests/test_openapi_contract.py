"""Slice 3: the API contract must expose every route the web app and voice agent use."""

from app.main import app

REQUIRED = {
    "/health",
    "/api/v1/customers",
    "/api/v1/dashboard/dues",
    "/api/v1/forecast",
    "/api/v1/forecast/what-if",
    "/api/v1/payments",
    "/api/v1/payments/ingest",
    "/api/v1/payments/{payment_id}/confirm-match",
    "/api/v1/agent/turn",
    "/api/v1/agent/confirm",
    "/api/v1/settings",
    "/api/v1/settings/bills",
    "/api/v1/payment-links/customer/{customer_id}",
    "/api/v1/payment-links/sync",
    "/api/v1/webhooks/razorpay",
}


def test_contract_has_all_routes():
    paths = set(app.openapi()["paths"])
    missing = REQUIRED - paths
    assert not missing, f"Missing routes: {sorted(missing)}"
