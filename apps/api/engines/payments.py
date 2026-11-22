"""Pure payment allocation over in-memory invoices; all money is Decimal.

One payment settles at most one invoice; any excess is reported as unallocated, not carried over.
"""

from decimal import Decimal
from datetime import datetime


def _is_payable(invoice: dict) -> bool:
    return invoice["paid_at"] is None and invoice["status"] not in ("paid", "draft")


def allocate_payment(
    invoices: list[dict],
    amount: Decimal,
    received_at: datetime,
    invoice_id: str | None = None,
) -> dict:
    """Apply a payment to one invoice and return the resulting status and amounts without mutating inputs."""
    if amount <= 0:
        raise ValueError("Amount must be positive")

    if invoice_id is not None:
        target = next((inv for inv in invoices if inv["id"] == invoice_id), None)
        if target is None or not _is_payable(target):
            raise ValueError("Invoice not payable")
    else:
        payable = [inv for inv in invoices if _is_payable(inv)]
        if not payable:
            raise ValueError("No unpaid invoice")
        target = min(payable, key=lambda inv: inv["due_date"])

    if amount >= target["amount"]:
        new_status = "paid"
        paid_at = received_at
    else:
        new_status = "partially_paid"
        paid_at = None

    return {
        "invoice_id": target["id"],
        "status": new_status,
        "paid_at": paid_at,
        "applied_amount": min(amount, target["amount"]),
        "unallocated": max(Decimal("0"), amount - target["amount"]),
    }
