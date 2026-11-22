"""Router tests for bills, payments and dashboard, using an in-memory fake repo (no Supabase)."""

from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import repo
from app.deps import get_current_business_id, get_supabase_client
from routers import bills, dashboard, payments


class FakeStore:
    """In-memory stand-in for the repo functions the routers call."""

    def __init__(self):
        self.bills = {}
        self.customers = []
        self.invoices = []
        self.payments = []

    # seeding helpers
    def add_bill(self, name="Rent", amount="1800", due_day=5, recurrence="monthly"):
        row = {
            "id": str(uuid4()),
            "business_id": "biz-1",
            "name": name,
            "amount": amount,
            "due_day": due_day,
            "recurrence": recurrence,
            "next_due_date": "2025-06-05",
        }
        self.bills[row["id"]] = row
        return row

    def add_customer(self, name, business_id="biz-1"):
        row = {"id": str(uuid4()), "business_id": business_id, "name": name, "status": "active"}
        self.customers.append(row)
        return row

    def add_invoice(self, customer_id, status="sent", due_date="2025-06-05", amount="2500"):
        row = {
            "id": str(uuid4()),
            "business_id": "biz-1",
            "customer_id": customer_id,
            "period": "2025-06",
            "amount": amount,
            "due_date": due_date,
            "status": status,
            "paid_at": None,
        }
        self.invoices.append(row)
        return row

    # fake repo functions
    def insert_bill(self, client, business_id, data):
        row = {**data, "id": str(uuid4()), "business_id": business_id}
        self.bills[row["id"]] = row
        return dict(row)

    def list_bills(self, client, business_id):
        return [dict(b) for b in self.bills.values() if b["business_id"] == business_id]

    def get_bill(self, client, business_id, bill_id):
        row = self.bills.get(bill_id)
        if row is None or row["business_id"] != business_id:
            return None
        return dict(row)

    def update_bill(self, client, business_id, bill_id, data):
        row = self.bills.get(bill_id)
        if row is None or row["business_id"] != business_id:
            return None
        row.update(data)
        return dict(row)

    def get_customer(self, client, business_id, customer_id):
        for c in self.customers:
            if c["id"] == customer_id and c["business_id"] == business_id:
                return dict(c)
        return None

    def list_customers(self, client, business_id, status, batch):
        return [dict(c) for c in self.customers if c["business_id"] == business_id]

    def list_invoices_for_customer(self, client, business_id, customer_id):
        return [
            dict(i)
            for i in self.invoices
            if i["business_id"] == business_id and i["customer_id"] == customer_id
        ]

    def list_invoices(self, client, business_id, status, customer_id, period):
        return [dict(i) for i in self.invoices if i["business_id"] == business_id]

    def update_invoice(self, client, business_id, invoice_id, data):
        for i in self.invoices:
            if i["id"] == invoice_id and i["business_id"] == business_id:
                i.update(data)
                return dict(i)
        return None

    def insert_payment(self, client, row):
        clean = {key: value for key, value in row.items() if key != "customer_id"}
        inserted = {**clean, "id": str(uuid4())}
        self.payments.append(inserted)
        return dict(inserted)


@pytest.fixture
def fake(monkeypatch):
    store = FakeStore()
    for name in (
        "insert_bill",
        "list_bills",
        "get_bill",
        "update_bill",
        "get_customer",
        "list_customers",
        "list_invoices_for_customer",
        "list_invoices",
        "update_invoice",
        "insert_payment",
    ):
        monkeypatch.setattr(repo, name, getattr(store, name))
    return store


@pytest.fixture
def client(fake):
    app = FastAPI()
    app.include_router(bills.router)
    app.include_router(payments.router)
    app.include_router(dashboard.router)
    app.dependency_overrides[get_current_business_id] = lambda: "biz-1"
    app.dependency_overrides[get_supabase_client] = lambda: object()
    return TestClient(app)


def test_patch_bill_null_amount_returns_422_and_keeps_amount(client, fake):
    bill = fake.add_bill(amount="1800")

    response = client.patch(f"/bills/{bill['id']}", json={"amount": None})
    assert response.status_code == 422
    assert fake.bills[bill["id"]]["amount"] == "1800"


def test_patch_bill_null_amount_with_name_keeps_amount(client, fake):
    bill = fake.add_bill(name="Electricity", amount="1800")

    response = client.patch(f"/bills/{bill['id']}", json={"name": "Power", "amount": None})
    assert response.status_code == 200
    assert fake.bills[bill["id"]]["name"] == "Power"
    assert fake.bills[bill["id"]]["amount"] == "1800"


def test_patch_bill_amount_is_stored_as_string(client, fake):
    bill = fake.add_bill(amount="1800")

    response = client.patch(f"/bills/{bill['id']}", json={"amount": 2000})
    assert response.status_code == 200
    assert fake.bills[bill["id"]]["amount"] == "2000"
    assert isinstance(fake.bills[bill["id"]]["amount"], str)


def test_patch_bill_empty_body_returns_422(client, fake):
    bill = fake.add_bill()

    response = client.patch(f"/bills/{bill['id']}", json={})
    assert response.status_code == 422


def test_patch_unknown_bill_returns_404(client, fake):
    response = client.patch("/bills/does-not-exist", json={"name": "X"})
    assert response.status_code == 404


def test_post_payment_marks_invoice_paid_and_omits_customer_id(client, fake):
    customer = fake.add_customer("Ravi")
    invoice = fake.add_invoice(customer["id"], status="sent", amount="2500")

    response = client.post(
        "/payments",
        json={"customer_id": customer["id"], "amount": "2500", "method": "cash"},
    )
    assert response.status_code == 201
    assert fake.invoices[0]["id"] == invoice["id"]
    assert fake.invoices[0]["status"] == "paid"
    assert len(fake.payments) == 1
    assert "customer_id" not in fake.payments[0]


def test_post_payment_zero_amount_returns_422(client, fake):
    customer = fake.add_customer("Ravi")
    fake.add_invoice(customer["id"], amount="2500")

    response = client.post(
        "/payments",
        json={"customer_id": customer["id"], "amount": 0, "method": "cash"},
    )
    assert response.status_code == 422


def test_post_payment_unknown_customer_returns_404(client, fake):
    response = client.post(
        "/payments",
        json={"customer_id": "does-not-exist", "amount": "2500", "method": "cash"},
    )
    assert response.status_code == 404


def test_dashboard_dues_totals_sum_unpaid_invoices(client, fake):
    aisha = fake.add_customer("Aisha Khan")
    fake.add_invoice(aisha["id"], status="sent", due_date="2025-06-05", amount="2500")
    fake.add_invoice(aisha["id"], status="paid", due_date="2025-05-05", amount="2500")

    response = client.get("/dashboard/dues")
    assert response.status_code == 200
    body = response.json()
    assert "rows" in body
    assert "totals" in body
    assert Decimal(str(body["totals"]["total_outstanding"])) == Decimal("2500")
    assert any(row["customer_name"] == "Aisha Khan" for row in body["rows"])


def test_app_mounts_routes_under_api_v1_and_health_at_root():
    from app.main import app as main_app

    client = TestClient(main_app)
    response = client.get("/health")
    assert response.status_code == 200
    schema_paths = main_app.openapi()["paths"]
    assert "/api/v1/dashboard/dues" in schema_paths
