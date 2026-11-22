"""Pure dues computation over in-memory invoices; all money is Decimal.

Unpaid means paid_at is None and status is neither 'paid' nor 'draft'.
"""

from decimal import Decimal
from datetime import date, datetime


def _is_unpaid(invoice: dict) -> bool:
    return invoice["paid_at"] is None and invoice["status"] not in ("paid", "draft")


def compute_dues(invoices: list[dict], customers: dict[str, dict], today: date) -> dict:
    """Return per-customer dues rows sorted by priority, plus outstanding totals."""
    unpaid = [inv for inv in invoices if _is_unpaid(inv)]

    grouped: dict[str, list[dict]] = {}
    for inv in unpaid:
        grouped.setdefault(inv["customer_id"], []).append(inv)

    rows: list[dict] = []
    for customer_id, invs in grouped.items():
        total_due = sum((i["amount"] for i in invs), Decimal("0"))
        oldest_due_date = min(i["due_date"] for i in invs)
        days_late = max(0, (today - oldest_due_date).days)
        rows.append(
            {
                "customer_id": customer_id,
                "customer_name": customers[customer_id]["name"],
                "total_due": total_due,
                "oldest_due_date": oldest_due_date,
                "days_late": days_late,
                "invoice_count": len(invs),
                "priority": total_due * Decimal(days_late),
            }
        )
    rows.sort(key=lambda r: (-r["priority"], r["customer_name"]))

    total_outstanding = sum((i["amount"] for i in unpaid), Decimal("0"))
    overdue_count = sum(1 for i in unpaid if i["due_date"] < today)

    paid_this_month = [
        inv
        for inv in invoices
        if inv["paid_at"] is not None
        and inv["paid_at"].year == today.year
        and inv["paid_at"].month == today.month
    ]
    collected_this_month = sum((i["amount"] for i in paid_this_month), Decimal("0"))
    recovered_this_month = sum(
        (i["amount"] for i in paid_this_month if i["paid_at"].date() > i["due_date"]),
        Decimal("0"),
    )

    return {
        "rows": rows,
        "totals": {
            "total_outstanding": total_outstanding,
            "overdue_count": overdue_count,
            "collected_this_month": collected_this_month,
            "recovered_this_month": recovered_this_month,
        },
    }
