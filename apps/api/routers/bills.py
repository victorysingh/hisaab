"""Bill routes: create, list and partially update recurring or one-time bills."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from app import repo
from app.deps import get_current_business_id, get_supabase_client
from app.schemas import BillCreate, BillOut, BillUpdate
from engines.bills import next_due_date

router = APIRouter(prefix="/bills", tags=["bills"])


@router.post("", status_code=201, response_model=BillOut)
def create_bill(
    payload: BillCreate,
    business_id: str = Depends(get_current_business_id),
    client=Depends(get_supabase_client),
) -> BillOut:
    """Create a bill; next_due_date is computed from the server's local today (date.today())."""
    data = payload.model_dump(mode="json")
    data["next_due_date"] = next_due_date(payload.due_day, date.today()).isoformat()
    data["amount"] = str(payload.amount)
    row = repo.insert_bill(client, business_id, data)
    return BillOut(**row)


@router.get("", response_model=list[BillOut])
def list_bills(
    business_id: str = Depends(get_current_business_id),
    client=Depends(get_supabase_client),
) -> list[BillOut]:
    """List the business's bills ordered by name."""
    rows = repo.list_bills(client, business_id)
    return [BillOut(**row) for row in rows]


@router.patch("/{bill_id}", response_model=BillOut)
def update_bill(
    bill_id: str,
    payload: BillUpdate,
    business_id: str = Depends(get_current_business_id),
    client=Depends(get_supabase_client),
) -> BillOut:
    """Apply only the fields the client sent to one bill; recomputes next_due_date when due_day changes."""
    data = payload.model_dump(mode="json", exclude_unset=True)
    if not data:
        raise HTTPException(422, "No fields to update")
    if "amount" in data:
        data["amount"] = str(payload.amount)
    if "due_day" in data:
        data["next_due_date"] = next_due_date(data["due_day"], date.today()).isoformat()
    row = repo.update_bill(client, business_id, bill_id, data)
    if row is None:
        raise HTTPException(404, "Bill not found")
    return BillOut(**row)
