"""Router tests for customers and invoices, using an in-memory fake repo (no Supabase)."""

from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import repo
from app.deps import get_current_business_id, get_supabase_client
from routers import customers, invoices


class FakeStore:
    """In-memory stand-in for the repo functions the routers call."""

    def __init__(self):
        self.customers = []
        self.invoices = []
        self.payments = []
        self.inserted_invoice_rows = []

    # seeding helpers
    def add_customer(self, name, status="active", monthly_fee="3000", due_day=5, batch=None, business_id="biz-1"):
        row = {
            "id": str(uuid4()),
            "business_id": business_id,
            "name": name,
            "phone": None,
            "guardian_name": None,
            "monthly_fee": monthly_fee,
            "due_day": due_day,
            "batch": batch,
            "status": status,
        }
        self.customers.append(row)
        return row

    def add_invoice(self, customer_id, period="2025-06", status="sent", due_date="2025-06-05", amount="3000"):
        row = {
            "id": str(uuid4()),
            "business_id": "biz-1",
            "customer_id": customer_id,
            "period": period,
            "amount": amount,
            "due_date": due_date,
            "status": status,
            "paid_at": None,
        }
        self.invoices.append(row)
        return row

    # fake repo functions
    def insert_customer(self, client, business_id, data):
        row = {**data, "id": str(uuid4()), "business_id": business_id}
        self.customers.append(row)
        return dict(row)

    def list_customers(self, client, business_id, status, batch):
        rows = [c for c in self.customers if c["business_id"] == business_id]
        if status is not None:
            rows = [c for c in rows if c["status"] == status]
        if batch is not None:
            rows = [c for c in rows if c["batch"] == batch]
        return [dict(c) for c in rows]

    def get_customer(self, client, business_id, customer_id):
        for c in self.customers:
            if c["id"] == customer_id and c["business_id"] == business_id:
                return dict(c)
        return None

    def update_customer(self, client, business_id, customer_id, data):
        for c in self.customers:
            if c["id"] == customer_id and c["business_id"] == business_id:
                c.update(data)
                return dict(c)
        return None

    def list_invoices_for_customer(self, client, business_id, customer_id):
        return [
            dict(i)
            for i in self.invoices
            if i["business_id"] == business_id and i["customer_id"] == customer_id
        ]

    def list_payments_for_customer(self, client, business_id, customer_id):
        invoice_ids = {i["id"] for i in self.list_invoices_for_customer(client, business_id, customer_id)}
        return [dict(p) for p in self.payments if p["invoice_id"] in invoice_ids]

    def list_active_customers(self, client, business_id):
        return [dict(c) for c in self.customers if c["business_id"] == business_id and c["status"] == "active"]

    def existing_periods(self, client, business_id, period):
        return {
            i["customer_id"]
            for i in self.invoices
            if i["business_id"] == business_id and i["period"] == period
        }

    def insert_invoices(self, client, rows):
        if not rows:
            return []
        inserted = []
        for row in rows:
            self.inserted_invoice_rows.append(row)
            invoice = {**row, "id": str(uuid4()), "paid_at": None}
            self.invoices.append(invoice)
            inserted.append(dict(invoice))
        return inserted

    def list_invoices(self, client, business_id, status, customer_id, period):
        rows = [i for i in self.invoices if i["business_id"] == business_id]
        if status is not None:
            rows = [i for i in rows if i["status"] == status]
        if customer_id is not None:
            rows = [i for i in rows if i["customer_id"] == customer_id]
        if period is not None:
            rows = [i for i in rows if i["period"] == period]
        return [dict(i) for i in rows]


@pytest.fixture
def fake(monkeypatch):
    store = FakeStore()
    for name in (
        "insert_customer",
        "list_customers",
        "get_customer",
        "update_customer",
        "list_invoices_for_customer",
        "list_payments_for_customer",
        "list_active_customers",
        "existing_periods",
        "insert_invoices",
        "list_invoices",
    ):
        monkeypatch.setattr(repo, name, getattr(store, name))
    return store


@pytest.fixture
def client(fake):
    app = FastAPI()
    app.include_router(customers.router)
    app.include_router(invoices.router)
    app.dependency_overrides[get_current_business_id] = lambda: "biz-1"
    app.dependency_overrides[get_supabase_client] = lambda: object()
    return TestClient(app)


def test_create_customer_returns_201(client, fake):
    response = client.post(
        "/customers",
        json={"name": "Asha", "monthly_fee": 3000, "due_day": 5},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Asha"
    assert Decimal(str(body["monthly_fee"])) == Decimal("3000")
    assert len(fake.customers) == 1


def test_create_customer_due_day_29_is_422(client, fake):
    response = client.post(
        "/customers",
        json={"name": "Ravi", "monthly_fee": 3000, "due_day": 29},
    )
    assert response.status_code == 422
    assert fake.customers == []


def test_list_customers_filters_by_status_and_batch(client, fake):
    fake.add_customer("Active A", status="active", batch="Class9")
    fake.add_customer("Paused B", status="paused", batch="Class10")
    fake.add_customer("Active C", status="active", batch=None)

    active = client.get("/customers", params={"status": "active"})
    assert active.status_code == 200
    assert {c["name"] for c in active.json()} == {"Active A", "Active C"}

    batch = client.get("/customers", params={"batch": "Class9"})
    assert batch.status_code == 200
    assert {c["name"] for c in batch.json()} == {"Active A"}


def test_get_customer_detail_and_404(client, fake):
    customer = fake.add_customer("Meera")
    invoice = fake.add_invoice(customer["id"])
    fake.payments.append(
        {
            "id": str(uuid4()),
            "business_id": "biz-1",
            "invoice_id": invoice["id"],
            "customer_id": None,
            "amount": "3000",
            "method": "cash",
            "source": "manual",
            "received_at": "2025-06-10T10:00:00+00:00",
            "match_status": "matched",
        }
    )

    response = client.get(f"/customers/{customer['id']}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == customer["id"]
    assert len(body["invoices"]) == 1
    assert len(body["payments"]) == 1

    missing = client.get("/customers/does-not-exist")
    assert missing.status_code == 404


def test_patch_customer_changes_only_sent_fields(client, fake):
    customer = fake.add_customer("Kiran", status="active", monthly_fee="2500", due_day=7, batch="Class9")

    response = client.patch(f"/customers/{customer['id']}", json={"status": "paused"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "paused"
    assert body["name"] == "Kiran"
    assert Decimal(str(body["monthly_fee"])) == Decimal("2500")
    assert body["due_day"] == 7
    assert body["batch"] == "Class9"

    unknown = client.patch("/customers/does-not-exist", json={"status": "paused"})
    assert unknown.status_code == 404

    empty = client.patch(f"/customers/{customer['id']}", json={})
    assert empty.status_code == 422


def test_generate_invoices_only_for_active_customers(client, fake):
    active = fake.add_customer("Active", status="active", due_day=5)
    paused = fake.add_customer("Paused", status="paused", due_day=9)

    response = client.post("/invoices/generate", params={"period": "2025-06"})
    assert response.status_code == 200
    assert response.json() == {"period": "2025-06", "created": 1, "skipped": 0}

    created = [i for i in fake.invoices if i["period"] == "2025-06"]
    assert len(created) == 1
    invoice = created[0]
    assert invoice["customer_id"] == active["id"]
    assert invoice["due_date"] == "2025-06-05"
    assert Decimal(str(invoice["amount"])) == Decimal(str(active["monthly_fee"]))
    assert invoice["status"] == "sent"
    assert all(i["customer_id"] != paused["id"] for i in fake.invoices)


def test_generate_invoices_twice_creates_no_duplicates(client, fake):
    fake.add_customer("A", status="active", due_day=5)
    fake.add_customer("B", status="active", due_day=10)
    fake.add_customer("C", status="paused", due_day=15)

    first = client.post("/invoices/generate", params={"period": "2025-06"})
    assert first.json()["created"] == 2

    second = client.post("/invoices/generate", params={"period": "2025-06"})
    assert second.status_code == 200
    body = second.json()
    assert body["created"] == 0
    assert body["skipped"] == 2
    assert len(fake.invoices) == 2


def test_generate_invoices_rejects_bad_period(client, fake):
    assert client.post("/invoices/generate", params={"period": "2025-13"}).status_code == 422
    assert client.post("/invoices/generate", params={"period": "2025-6"}).status_code == 422


def test_list_invoices_filters_by_status_and_customer(client, fake):
    a = fake.add_customer("A")
    b = fake.add_customer("B")
    fake.add_invoice(a["id"], status="sent")
    fake.add_invoice(b["id"], status="paid")
    fake.add_invoice(b["id"], status="sent")

    sent = client.get("/invoices", params={"status": "sent"})
    assert sent.status_code == 200
    assert {i["status"] for i in sent.json()} == {"sent"}
    assert len(sent.json()) == 2

    by_customer = client.get("/invoices", params={"customer_id": b["id"]})
    assert by_customer.status_code == 200
    assert len(by_customer.json()) == 2
    assert {i["customer_id"] for i in by_customer.json()} == {b["id"]}


def test_generated_amount_is_sent_as_string_not_float(client, fake):
    fake.add_customer("Fee", status="active", monthly_fee="3000", due_day=5)

    response = client.post("/invoices/generate", params={"period": "2025-06"})
    assert response.status_code == 200

    assert len(fake.inserted_invoice_rows) == 1
    amount = fake.inserted_invoice_rows[0]["amount"]
    assert isinstance(amount, str)
    assert amount == "3000"
