"""Invoice routes: generate a billing period's invoices and list invoices."""

import re
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException

from app import repo
from app.deps import get_current_business_id, get_supabase_client
from app.schemas import GenerateResult, InvoiceOut

router = APIRouter(prefix="/invoices", tags=["invoices"])

_PERIOD_PATTERN = r"\d{4}-(0[1-9]|1[0-2])"


def _due_date(period: str, due_day: int) -> date:
    """Return the due date for a YYYY-MM period on the given day of that month."""
    return date(int(period[:4]), int(period[5:7]), due_day)


@router.post("/generate", response_model=GenerateResult)
def generate_invoices(
    period: str,
    business_id: str = Depends(get_current_business_id),
    client=Depends(get_supabase_client),
) -> GenerateResult:
    """Create one invoice per active customer for the period, skipping those already invoiced."""
    if not re.fullmatch(_PERIOD_PATTERN, period):
        raise HTTPException(422, "period must be YYYY-MM")

    customers = repo.list_active_customers(client, business_id)
    already = repo.existing_periods(client, business_id, period)

    skipped = 0
    rows = []
    for c in customers:
        if c["id"] in already:
            skipped += 1
            continue
        rows.append(
            {
                "customer_id": c["id"],
                "business_id": business_id,
                "period": period,
                "amount": str(Decimal(str(c["monthly_fee"]))),
                "due_date": _due_date(period, c["due_day"]).isoformat(),
                "status": "sent",
            }
        )

    inserted = repo.insert_invoices(client, rows)
    return GenerateResult(period=period, created=len(inserted), skipped=skipped)


@router.get("", response_model=list[InvoiceOut])
def list_invoices(
    status: str | None = None,
    customer_id: str | None = None,
    period: str | None = None,
    business_id: str = Depends(get_current_business_id),
    client=Depends(get_supabase_client),
) -> list[InvoiceOut]:
    """List the business's invoices, optionally filtered by status, customer and period."""
    rows = repo.list_invoices(client, business_id, status, customer_id, period)
    return [InvoiceOut(**row) for row in rows]
