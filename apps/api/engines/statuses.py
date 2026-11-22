"""Pure status refresh for invoices; returns new dicts and never mutates inputs."""

from datetime import date


def refresh_statuses(invoices: list[dict], today: date) -> list[dict]:
    """Return copies of invoices, marking unpaid past-due ones as 'overdue'."""
    result: list[dict] = []
    for invoice in invoices:
        updated = dict(invoice)
        if (
            invoice["paid_at"] is None
            and invoice["status"] not in ("paid", "draft")
            and invoice["due_date"] < today
        ):
            updated["status"] = "overdue"
        result.append(updated)
    return result
