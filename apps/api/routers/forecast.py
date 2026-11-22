"""Forecast routes: cash forecast and what-if scenarios.

All maths happens in engines/forecast.py. This router only loads data from Supabase,
passes it in with `today`, and returns the engine's result.
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.config import get_settings
from app.deps import get_current_business_id, get_supabase_client
from engines.forecast import build_forecast, what_if

router = APIRouter(prefix="/forecast", tags=["forecast"])


class WhatIfRequest(BaseModel):
    days: int = Field(60, description="30, 60 or 90")
    changes: list[dict] = Field(default_factory=list)


def _today() -> date:
    demo_today = getattr(get_settings(), "demo_today", "") or ""
    return date.fromisoformat(demo_today) if demo_today else date.today()


def _load_inputs(client, business_id: str) -> dict:
    business = (
        client.table("businesses").select("opening_balance, safety_buffer")
        .eq("id", business_id).limit(1).execute()
    ).data
    if not business:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Business not found")
    customers = (
        client.table("customers").select("id, name, monthly_fee, due_day, status")
        .eq("business_id", business_id).execute()
    ).data or []
    invoices = (
        client.table("invoices").select("id, customer_id, period, amount, due_date, status, paid_at")
        .eq("business_id", business_id).limit(5000).execute()
    ).data or []
    bills = (
        client.table("bills").select("id, name, amount, due_day, recurrence, next_due_date")
        .eq("business_id", business_id).execute()
    ).data or []
    return {
        "start_balance": business[0].get("opening_balance") or 0,
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
    days: int = Query(60),
    business_id: str = Depends(get_current_business_id),
    client=Depends(get_supabase_client),
) -> dict:
    _check_days(days)
    inputs = _load_inputs(client, business_id)
    return build_forecast(today=_today(), days=days, **inputs)


@router.post("/what-if")
def post_what_if(
    body: WhatIfRequest,
    business_id: str = Depends(get_current_business_id),
    client=Depends(get_supabase_client),
) -> dict:
    _check_days(body.days)
    inputs = _load_inputs(client, business_id)
    return what_if(baseline_kwargs={"today": _today(), "days": body.days, **inputs}, changes=body.changes)
