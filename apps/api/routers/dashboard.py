"""Dashboard routes: outstanding dues per customer with totals."""

from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends

from app import repo
from app.deps import get_current_business_id, get_supabase_client
from app.schemas import DuesResponse, DuesRow, DuesTotals
from engines.dues import compute_dues
from engines.statuses import refresh_statuses

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _parse_ts(value):
    """Parse a Supabase timestamp (str, or None) into a datetime, or return None."""
    if value is None:
        return None
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


@router.get("/dues", response_model=DuesResponse)
def get_dues(
    business_id: str = Depends(get_current_business_id),
    client=Depends(get_supabase_client),
) -> DuesResponse:
    """Return per-customer outstanding dues ordered by priority (temporary: total_due x days_late), plus totals."""
    customers = repo.list_customers(client, business_id, None, None)
    names = {c["id"]: c["name"] for c in customers}

    rows = [
        {
            "id": row["id"],
            "customer_id": row["customer_id"],
            "amount": Decimal(str(row["amount"])),
            "due_date": date.fromisoformat(str(row["due_date"])[:10]),
            "status": row["status"],
            "paid_at": _parse_ts(row.get("paid_at")),
        }
        for row in repo.list_invoices(client, business_id, None, None, None)
    ]

    today = date.today()
    refreshed = refresh_statuses(rows, today)
    for original, current in zip(rows, refreshed):
        if current["status"] != original["status"]:
            repo.update_invoice(client, business_id, current["id"], {"status": "overdue"})

    result = compute_dues(
        refreshed,
        {cid: {"name": name} for cid, name in names.items()},
        today,
    )
    return DuesResponse(
        rows=[DuesRow(**r) for r in result["rows"]],
        totals=DuesTotals(**result["totals"]),
    )
