"""Forecast routes: cash forecast and what-if scenarios.

All maths happens in engines/forecast.py. This router only loads data from Supabase,
passes it in with `today`, and returns the engine's result.
"""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.config import get_settings
from app.deps import get_current_business_id, get_supabase_client
from engines.forecast import build_forecast, what_if

router = APIRouter(prefix="/forecast", tags=["forecast"])


class WhatIfRequest(BaseModel):
    days: int = Field(60, description="30, 60 or 90")
    changes: list[dict] = Field(
        default_factory=list,
        description=(
            'e.g. [{"type": "delay", "customer_id": "...", "days": 15}], '
            '[{"type": "drop", "customer_ids": ["..."], "from_period": "2026-12"}], '
            '[{"type": "new_bill", "name": "AC repair", "amount": 15000, "date": "2026-11-30", "recurrence": "once"}], '
            '[{"type": "new_customer", "name": "New student", "monthly_fee": 2500, "start_period": "2026-12"}]'
        ),
    )


def _today() -> date:
    """DEMO_TODAY (YYYY-MM-DD) pins the date for rehearsals; otherwise the real date."""
    demo_today = getattr(get_settings(), "demo_today", "") or ""
    return date.fromisoformat(demo_today) if demo_today else date.today()


def _load_inputs(client, business_id: str, today: date | None = None) -> dict:
    """opening_balance is Priya's cash at the start of `today`; payments recorded today are added on top."""
    today = today or _today()
    business = (
        client.table("businesses")
        .select("opening_balance, safety_buffer")
        .eq("id", business_id)
        .limit(1)
        .execute()
    ).data
    if not business:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Business not found")

    customers = (
        client.table("customers")
        .select("id, name, monthly_fee, due_day, status")
        .eq("business_id", business_id)
        .execute()
    ).data or []

    invoices = (
        client.table("invoices")
        .select("id, customer_id, period, amount, due_date, status, paid_at")
        .eq("business_id", business_id)
        .limit(5000)
        .execute()
    ).data or []

    bills = (
        client.table("bills")
        .select("id, name, amount, due_day, recurrence, next_due_date")
        .eq("business_id", business_id)
        .execute()
    ).data or []

    received_today = (
        client.table("payments")
        .select("amount")
        .eq("business_id", business_id)
        .gte("received_at", today.isoformat())
        .execute()
    ).data or []
    cash_in_today = sum((Decimal(str(p.get("amount") or 0)) for p in received_today), Decimal("0"))

    return {
        "start_balance": Decimal(str(business[0].get("opening_balance") or 0)) + cash_in_today,
        "safety_buffer": business[0].get("safety_buffer") or 0,
        "customers": customers,
        "invoices": invoices,
        "bills": bills,
    }


def _check_days(days: int) -> None:
    if days not in (30, 60, 90):
        raise HTTPException(422, "days must be 30, 60 or 90")


@router.get("")
def get_forecast(
    days: int = Query(60, description="30, 60 or 90"),
    business_id: str = Depends(get_current_business_id),
    client=Depends(get_supabase_client),
) -> dict:
    """Daily best / likely / worst balance, first shortfall, its causes and the assumptions."""
    _check_days(days)
    today = _today()
    inputs = _load_inputs(client, business_id, today)
    return build_forecast(today=today, days=days, **inputs)


@router.post("/what-if")
def post_what_if(
    body: WhatIfRequest,
    business_id: str = Depends(get_current_business_id),
    client=Depends(get_supabase_client),
) -> dict:
    """Same shape as GET /forecast with the changes applied, plus `baseline` (the unchanged forecast)."""
    _check_days(body.days)
    today = _today()
    inputs = _load_inputs(client, business_id, today)
    return what_if(baseline_kwargs={"today": today, "days": body.days, **inputs}, changes=body.changes)
