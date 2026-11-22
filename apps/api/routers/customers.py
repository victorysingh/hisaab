"""Customer routes: create, list, detail and partial update."""

from fastapi import APIRouter, Depends, HTTPException

from app import repo
from app.deps import get_current_business_id, get_supabase_client
from app.schemas import (
    CustomerCreate,
    CustomerDetail,
    CustomerOut,
    CustomerUpdate,
    InvoiceOut,
    PaymentOut,
)

router = APIRouter(prefix="/customers", tags=["customers"])


@router.post("", status_code=201, response_model=CustomerOut)
def create_customer(
    payload: CustomerCreate,
    business_id: str = Depends(get_current_business_id),
    client=Depends(get_supabase_client),
) -> CustomerOut:
    """Create a customer for the current business."""
    row = repo.insert_customer(client, business_id, payload.model_dump(mode="json"))
    return CustomerOut(**row)


@router.get("", response_model=list[CustomerOut])
def list_customers(
    status: str | None = None,
    batch: str | None = None,
    business_id: str = Depends(get_current_business_id),
    client=Depends(get_supabase_client),
) -> list[CustomerOut]:
    """List the business's customers, optionally filtered by status and batch."""
    rows = repo.list_customers(client, business_id, status, batch)
    return [CustomerOut(**row) for row in rows]


@router.get("/{customer_id}", response_model=CustomerDetail)
def get_customer(
    customer_id: str,
    business_id: str = Depends(get_current_business_id),
    client=Depends(get_supabase_client),
) -> CustomerDetail:
    """Return one customer with their invoices and payments."""
    customer = repo.get_customer(client, business_id, customer_id)
    if customer is None:
        raise HTTPException(404, "Customer not found")
    invoices = repo.list_invoices_for_customer(client, business_id, customer_id)
    payments = repo.list_payments_for_customer(client, business_id, customer_id)
    return CustomerDetail(
        **customer,
        invoices=[InvoiceOut(**i) for i in invoices],
        payments=[PaymentOut(**p) for p in payments],
    )


@router.patch("/{customer_id}", response_model=CustomerOut)
def update_customer(
    customer_id: str,
    payload: CustomerUpdate,
    business_id: str = Depends(get_current_business_id),
    client=Depends(get_supabase_client),
) -> CustomerOut:
    """Apply only the fields the client sent to one customer."""
    data = payload.model_dump(mode="json", exclude_unset=True, exclude_none=True)
    if not data:
        raise HTTPException(422, "No fields to update")
    row = repo.update_customer(client, business_id, customer_id, data)
    if row is None:
        raise HTTPException(404, "Customer not found")
    return CustomerOut(**row)
