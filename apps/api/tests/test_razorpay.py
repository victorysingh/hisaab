"""Tests for the Razorpay adapter and routes. No network: Razorpay is faked."""

import hashlib
import hmac
import json
import uuid

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters import payments as rzp

SECRET = "test-webhook-secret"


# ---------- fake Supabase ----------

class FakeDB:
    def __init__(self):
        self.tables = {
            "customers": [{"id": "r", "business_id": "biz", "name": "Rohan Sharma", "phone": "+91 90000 00001"}],
            "invoices": [
                {"id": "inv-old", "business_id": "biz", "customer_id": "r", "period": "2026-10", "amount": "3000",
                 "due_date": "2026-10-05", "status": "paid", "payment_link_id": None, "payment_link_url": None},
                {"id": "inv-nov", "business_id": "biz", "customer_id": "r", "period": "2026-11", "amount": "3000",
                 "due_date": "2026-11-05", "status": "overdue", "payment_link_id": None, "payment_link_url": None},
            ],
            "payments": [],
        }

    def table(self, name):
        return Query(self.tables[name])


class Query:
    def __init__(self, rows):
        self.rows, self.filters, self.op, self.payload = rows, [], "select", None

    def select(self, *_):
        return self

    def eq(self, k, v):
        self.filters.append((k, v))
        return self

    def limit(self, _):
        return self

    def insert(self, row):
        self.op, self.payload = "insert", row
        return self

    def update(self, row):
        self.op, self.payload = "update", row
        return self

    def execute(self):
        class R:
            data = None
        r = R()
        if self.op == "insert":
            row = {"id": str(uuid.uuid4()), **self.payload}
            self.rows.append(row)
            r.data = [row]
            return r
        hits = [x for x in self.rows if all(x.get(k) == v for k, v in self.filters)]
        if self.op == "update":
            for x in hits:
                x.update(self.payload)
        r.data = hits
        return r


@pytest.fixture
def setup(monkeypatch):
    from app import deps
    from routers import razorpay

    db = FakeDB()
    monkeypatch.setattr(rzp, "env", lambda name: {"RAZORPAY_KEY_ID": "rzp_test_x", "RAZORPAY_KEY_SECRET": "s",
                                                  "RAZORPAY_WEBHOOK_SECRET": SECRET}.get(name, ""))
    monkeypatch.setattr(razorpay, "resolve_demo_business_id", lambda: "biz")
    app = FastAPI()
    app.include_router(razorpay.router, prefix="/api/v1")
    app.dependency_overrides[deps.get_supabase_client] = lambda: db
    app.dependency_overrides[deps.get_current_business_id] = lambda: "biz"
    return TestClient(app), db, razorpay


# ---------- adapter ----------

def test_to_paise():
    assert rzp.to_paise("3000") == 300000
    assert rzp.to_paise("2500.50") == 250050


def test_verify_webhook_signature():
    body = b'{"event":"payment_link.paid"}'
    good = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    assert rzp.verify_webhook(body, good, SECRET)
    assert not rzp.verify_webhook(body, "bad", SECRET)
    assert not rzp.verify_webhook(body, None, SECRET)


def test_create_payment_link_sends_paise_and_reference(monkeypatch):
    monkeypatch.setattr(rzp, "env", lambda n: {"RAZORPAY_KEY_ID": "k", "RAZORPAY_KEY_SECRET": "s"}.get(n, ""))
    seen = {}

    def handler(request: httpx.Request):
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": "plink_1", "short_url": "https://rzp.io/i/abc", "status": "created"})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    link = rzp.create_payment_link(invoice_id="inv-nov", amount="3000", description="Rohan - Nov fees",
                                   customer_name="Rohan Sharma", phone="+91 90000 00001", http=http)
    assert link["short_url"] == "https://rzp.io/i/abc"
    assert seen["body"]["amount"] == 300000
    assert seen["body"]["reference_id"] == "inv-nov"
    assert seen["body"]["customer"]["contact"] == "+919000000001"


# ---------- routes ----------

def test_link_for_customer_uses_oldest_unpaid_and_is_reused(setup, monkeypatch):
    client, db, _ = setup
    calls = []
    monkeypatch.setattr(rzp, "create_payment_link", lambda **kw: calls.append(kw) or
                        {"id": "plink_9", "short_url": "https://rzp.io/i/xyz", "status": "created"})
    first = client.post("/api/v1/payment-links/customer/r").json()
    second = client.post("/api/v1/payment-links/customer/r").json()
    assert first["url"] == second["url"] == "https://rzp.io/i/xyz"
    assert first["invoice_id"] == "inv-nov" and second["reused"] is True
    assert len(calls) == 1


def test_webhook_marks_invoice_paid_once(setup):
    client, db, _ = setup
    event = {"event": "payment_link.paid", "payload": {
        "payment_link": {"entity": {"id": "plink_9", "reference_id": "inv-nov", "amount": 300000, "amount_paid": 300000}},
        "payment": {"entity": {"id": "pay_123", "amount": 300000, "method": "upi"}}}}
    body = json.dumps(event).encode()
    sig = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    r1 = client.post("/api/v1/webhooks/razorpay", content=body, headers={"X-Razorpay-Signature": sig}).json()
    r2 = client.post("/api/v1/webhooks/razorpay", content=body, headers={"X-Razorpay-Signature": sig}).json()
    assert r1["recorded"] is True and r2["recorded"] is False
    inv = next(i for i in db.tables["invoices"] if i["id"] == "inv-nov")
    assert inv["status"] == "paid"
    assert len(db.tables["payments"]) == 1 and db.tables["payments"][0]["source"] == "link_webhook"


def test_webhook_rejects_bad_signature(setup):
    client, db, _ = setup
    r = client.post("/api/v1/webhooks/razorpay", content=b"{}", headers={"X-Razorpay-Signature": "nope"})
    assert r.status_code == 400
    assert db.tables["payments"] == []


def test_sync_records_paid_links(setup, monkeypatch):
    client, db, _ = setup
    next(i for i in db.tables["invoices"] if i["id"] == "inv-nov")["payment_link_id"] = "plink_9"
    monkeypatch.setattr(rzp, "fetch_payment_link", lambda link_id: {
        "id": link_id, "status": "paid", "amount": 300000, "amount_paid": 300000,
        "payments": [{"payment_id": "pay_777", "method": "upi"}]})
    result = client.post("/api/v1/payment-links/sync").json()
    assert result["paid"] == ["inv-nov"]
    assert client.post("/api/v1/payment-links/sync").json()["paid"] == []
