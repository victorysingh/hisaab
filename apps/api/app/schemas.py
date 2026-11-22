"""Pydantic request and response models for customers, invoices, payments, bills and dues."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class CustomerCreate(BaseModel):
    """Payload for creating a customer."""

    name: str = Field(min_length=1)
    phone: str | None = None
    guardian_name: str | None = None
    monthly_fee: Decimal = Field(gt=0)
    due_day: int = Field(ge=1, le=28)
    batch: str | None = None
    status: Literal["active", "paused", "left"] = "active"


class CustomerUpdate(BaseModel):
    """Partial customer update; only fields the client sent should be applied."""

    name: str | None = Field(default=None, min_length=1)
    phone: str | None = None
    guardian_name: str | None = None
    monthly_fee: Decimal | None = Field(default=None, gt=0)
    due_day: int | None = Field(default=None, ge=1, le=28)
    batch: str | None = None
    status: Literal["active", "paused", "left"] | None = None


class CustomerOut(BaseModel):
    """A customer as returned by the API."""

    id: str
    name: str
    phone: str | None = None
    guardian_name: str | None = None
    monthly_fee: Decimal
    due_day: int
    batch: str | None = None
    status: Literal["active", "paused", "left"]


class InvoiceOut(BaseModel):
    """An invoice as returned by the API."""

    id: str
    customer_id: str
    period: str
    amount: Decimal
    due_date: date
    status: Literal["draft", "sent", "partially_paid", "paid", "overdue"]
    paid_at: datetime | None = None


class PaymentCreate(BaseModel):
    """Payload for recording a payment received from a customer."""

    customer_id: str
    amount: Decimal = Field(gt=0)
    method: Literal["upi", "cash", "card", "other"] = "cash"
    received_at: datetime | None = None
    invoice_id: str | None = None
    payer_text: str | None = None
    upi_ref: str | None = None


class PaymentOut(BaseModel):
    """A payment as returned by the API."""

    id: str
    business_id: str
    invoice_id: str | None
    customer_id: str | None = None
    amount: Decimal
    method: str
    source: str
    received_at: datetime
    match_status: str


class BillCreate(BaseModel):
    """Payload for creating a recurring or one-time bill."""

    name: str = Field(min_length=1)
    amount: Decimal = Field(gt=0)
    due_day: int = Field(ge=1, le=28)
    recurrence: Literal["monthly", "once"] = "monthly"
    category: str | None = None


class BillUpdate(BaseModel):
    """Partial bill update; only fields the client sent should be applied."""

    name: str | None = Field(default=None, min_length=1)
    amount: Decimal | None = Field(default=None, gt=0)
    due_day: int | None = Field(default=None, ge=1, le=28)
    recurrence: Literal["monthly", "once"] | None = None
    category: str | None = None


class BillOut(BaseModel):
    """A bill as returned by the API."""

    id: str
    name: str
    amount: Decimal
    due_day: int
    recurrence: Literal["monthly", "once"]
    category: str | None = None
    next_due_date: date | None = None


class CustomerDetail(CustomerOut):
    """A customer with their invoices and payments."""

    invoices: list[InvoiceOut] = []
    payments: list[PaymentOut] = []


class DuesRow(BaseModel):
    """One customer's outstanding dues summary."""

    customer_id: str
    customer_name: str
    total_due: Decimal
    oldest_due_date: date
    days_late: int
    invoice_count: int
    priority: Decimal


class DuesTotals(BaseModel):
    """Aggregate totals shown alongside the dues list."""

    total_outstanding: Decimal
    overdue_count: int
    collected_this_month: Decimal
    recovered_this_month: Decimal


class DuesResponse(BaseModel):
    """Dues rows plus their totals."""

    rows: list[DuesRow]
    totals: DuesTotals


class GenerateResult(BaseModel):
    """Result of generating invoices for a billing period."""

    period: str
    created: int
    skipped: int
