"""Settings routes: business details and bills, for the Settings screen.

GET    /settings                 -> {business: {...}, bills: [...]}
PATCH  /settings                 {name?, opening_balance?, safety_buffer?}
POST   /settings/bills           {name, amount, due_day, recurrence, next_due_date?}
DELETE /settings/bills/{bill_id}
"""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.deps import get_current_business_id, get_supabase_client
from routers.forecast import _today

router = APIRouter(prefix="/settings", tags=["settings"])


class BusinessUpdate(BaseModel):
    name: str | None = None
    opening_balance: Decimal | None = None
    safety_buffer: Decimal | None = Field(default=None, ge=0)


class BillIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    amount: Decimal = Field(gt=0)
    due_day: int = Field(default=1, ge=1, le=31)
    recurrence: str = Field(default="monthly", pattern="^(monthly|once)$")
    next_due_date: date | None = None
    category: str | None = None


def _next_due(due_day: int, today: date) -> date:
    import calendar
    day = min(due_day, calendar.monthrange(today.year, today.month)[1])
    d = date(today.year, today.month, day)
    if d > today:
        return d
    y, m = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
    return date(y, m, min(due_day, calendar.monthrange(y, m)[1]))


@router.get("")
def get_settings_view(business_id: str = Depends(get_current_business_id),
                      client=Depends(get_supabase_client)) -> dict:
    business = (
        client.table("businesses").select("id, name, opening_balance, safety_buffer")
        .eq("id", business_id).limit(1).execute()
    ).data
    if not business:
        raise HTTPException(404, "Business not found")
    bills = (
        client.table("bills").select("id, name, amount, due_day, recurrence, next_due_date, category")
        .eq("business_id", business_id).execute()
    ).data or []
    bills.sort(key=lambda b: (b.get("recurrence") != "monthly", b.get("due_day") or 0, b.get("name") or ""))
    return {"business": business[0], "bills": bills}


@router.patch("")
def update_business(body: BusinessUpdate, business_id: str = Depends(get_current_business_id),
                    client=Depends(get_supabase_client)) -> dict:
    data = {k: (str(v) if isinstance(v, Decimal) else v)
            for k, v in body.model_dump(exclude_none=True).items()}
    if not data:
        raise HTTPException(422, "Nothing to update")
    client.table("businesses").update(data).eq("id", business_id).execute()
    return {"ok": True, "updated": list(data)}


@router.post("/bills")
def add_bill(body: BillIn, business_id: str = Depends(get_current_business_id),
             client=Depends(get_supabase_client)) -> dict:
    if body.recurrence == "once" and body.next_due_date is None:
        raise HTTPException(422, "A one-off bill needs a date")
    next_due = body.next_due_date or _next_due(body.due_day, _today())
    row = {
        "business_id": business_id,
        "name": body.name.strip(),
        "amount": str(body.amount),
        "due_day": next_due.day if body.recurrence == "once" else body.due_day,
        "recurrence": body.recurrence,
        "next_due_date": next_due.isoformat(),
        "category": body.category,
    }
    inserted = client.table("bills").insert(row).execute().data
    return inserted[0] if inserted else row


@router.delete("/bills/{bill_id}")
def delete_bill(bill_id: str, business_id: str = Depends(get_current_business_id),
                client=Depends(get_supabase_client)) -> dict:
    found = (
        client.table("bills").select("id").eq("id", bill_id).eq("business_id", business_id).limit(1).execute()
    ).data
    if not found:
        raise HTTPException(404, "Bill not found")
    client.table("bills").delete().eq("id", bill_id).eq("business_id", business_id).execute()
    return {"ok": True}
