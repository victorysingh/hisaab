"""Payment routes: record a manual payment and allocate it to an invoice."""

import logging
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException

from app import repo
from app.deps import get_current_business_id, get_supabase_client
from app.schemas import PaymentCreate, PaymentOut
from engines.payments import allocate_payment

router = APIRouter(prefix="/payments", tags=["payments"])
logger = logging.getLogger(__name__)


def _parse_ts(value):
    """Parse a Supabase timestamp (str, or None) into a datetime, or return None."""
    if value is None:
        return None
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _to_invoice(row: dict) -> dict:
    """Convert a raw invoice row into the types the engine expects."""
    return {
        **row,
        "amount": Decimal(str(row["amount"])),
        "due_date": date.fromisoformat(str(row["due_date"])[:10]),
        "paid_at": _parse_ts(row.get("paid_at")),
    }


@router.post("", status_code=201, response_model=PaymentOut)
def create_payment(
    payload: PaymentCreate,
    business_id: str = Depends(get_current_business_id),
    client=Depends(get_supabase_client),
) -> PaymentOut:
    """Record a manual payment, allocate it to one invoice and persist both changes."""
    customer = repo.get_customer(client, business_id, payload.customer_id)
    if customer is None:
        raise HTTPException(404, "Customer not found")

    invoices = [
        _to_invoice(row)
        for row in repo.list_invoices_for_customer(client, business_id, payload.customer_id)
    ]
    received = payload.received_at or datetime.now(timezone.utc)

    try:
        result = allocate_payment(invoices, payload.amount, received, payload.invoice_id)
    except ValueError as exc:
        raise HTTPException(422, str(exc))

    updated = repo.update_invoice(
        client,
        business_id,
        result["invoice_id"],
        {
            "status": result["status"],
            "paid_at": result["paid_at"].isoformat() if result["paid_at"] else None,
        },
    )
    if updated is None:
        raise HTTPException(404, "Invoice not found")

    # The response schema is fixed, so the unallocated amount is only logged here.
    logger.info(
        "payment for customer %s: applied %s to invoice %s, unallocated %s",
        payload.customer_id,
        result["applied_amount"],
        result["invoice_id"],
        result["unallocated"],
    )

    row = {
        "business_id": business_id,
        "customer_id": payload.customer_id,
        "invoice_id": result["invoice_id"],
        "amount": str(payload.amount),
        "method": payload.method,
        "source": "manual",
        "payer_text": payload.payer_text,
        "upi_ref": payload.upi_ref,
        "received_at": received.isoformat(),
        "match_status": "matched",
    }
    inserted = repo.insert_payment(client, row)
    return PaymentOut(**{**inserted, "customer_id": payload.customer_id})
