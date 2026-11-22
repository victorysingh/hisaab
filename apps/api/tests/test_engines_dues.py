import copy
from datetime import date, datetime
from decimal import Decimal

import pytest

from engines.statuses import refresh_statuses
from engines.dues import compute_dues

TODAY = date(2025, 6, 10)


def inv(id, customer_id, amount, due_date, status="sent", paid_at=None):
    return {
        "id": id,
        "customer_id": customer_id,
        "amount": Decimal(amount),
        "due_date": due_date,
        "status": status,
        "paid_at": paid_at,
    }


CUSTOMERS = {"c1": {"name": "Asha"}, "c2": {"name": "Ravi"}, "c3": {"name": "Meera"}}


# refresh_statuses

def test_refresh_marks_unpaid_past_due_sent_as_overdue():
    invoices = [{"id": "a", "due_date": date(2025, 6, 1), "status": "sent", "paid_at": None}]
    result = refresh_statuses(invoices, TODAY)
    assert result[0]["status"] == "overdue"


def test_refresh_leaves_paid_invoice_as_paid():
    invoices = [
        {
            "id": "a",
            "due_date": date(2025, 6, 1),
            "status": "paid",
            "paid_at": datetime(2025, 6, 2, 10, 0),
        }
    ]
    result = refresh_statuses(invoices, TODAY)
    assert result[0]["status"] == "paid"


def test_refresh_leaves_draft_as_draft():
    invoices = [{"id": "a", "due_date": date(2025, 6, 1), "status": "draft", "paid_at": None}]
    result = refresh_statuses(invoices, TODAY)
    assert result[0]["status"] == "draft"


def test_refresh_does_not_mutate_inputs():
    invoices = [{"id": "a", "due_date": date(2025, 6, 1), "status": "sent", "paid_at": None}]
    before = copy.deepcopy(invoices)
    refresh_statuses(invoices, TODAY)
    assert invoices == before


# compute_dues

def test_rows_only_for_customers_with_unpaid_invoices():
    invoices = [
        inv("a", "c1", "1000", date(2025, 6, 1)),
        inv("b", "c2", "500", date(2025, 6, 1), status="paid", paid_at=datetime(2025, 6, 2, 9, 0)),
    ]
    result = compute_dues(invoices, CUSTOMERS, TODAY)
    assert [r["customer_id"] for r in result["rows"]] == ["c1"]


def test_total_due_count_and_oldest_due_date_for_one_customer():
    invoices = [
        inv("a", "c1", "1000", date(2025, 5, 1)),
        inv("b", "c1", "2000", date(2025, 6, 20)),
    ]
    row = compute_dues(invoices, CUSTOMERS, TODAY)["rows"][0]
    assert row["total_due"] == Decimal("3000")
    assert row["invoice_count"] == 2
    assert row["oldest_due_date"] == date(2025, 5, 1)


def test_days_late_from_oldest_and_zero_for_future_due():
    late = compute_dues([inv("a", "c1", "1000", date(2025, 5, 1))], CUSTOMERS, TODAY)
    assert late["rows"][0]["days_late"] == (TODAY - date(2025, 5, 1)).days

    future = compute_dues([inv("b", "c1", "1000", date(2025, 7, 1))], CUSTOMERS, TODAY)
    assert future["rows"][0]["days_late"] == 0


def test_priority_is_total_due_times_days_late_and_rows_sorted_desc():
    invoices = [
        inv("a", "c1", "3000", date(2025, 6, 1)),   # Asha: 3000 * 9 = 27000
        inv("b", "c2", "1000", date(2025, 3, 10)),  # Ravi: 1000 * 92 = 92000
    ]
    rows = compute_dues(invoices, CUSTOMERS, TODAY)["rows"]
    assert rows[0]["customer_id"] == "c2"
    assert rows[0]["priority"] == Decimal("1000") * Decimal(92)
    assert rows[1]["customer_id"] == "c1"
    assert rows[1]["priority"] == Decimal("3000") * Decimal(9)


def test_total_outstanding_sums_all_unpaid():
    invoices = [
        inv("a", "c1", "1000", date(2025, 5, 1)),
        inv("b", "c2", "250", date(2025, 6, 20)),
        inv("c", "c3", "700", date(2025, 6, 1), status="draft"),
        inv("d", "c3", "400", date(2025, 6, 1), status="paid", paid_at=datetime(2025, 6, 3, 8, 0)),
    ]
    totals = compute_dues(invoices, CUSTOMERS, TODAY)["totals"]
    assert totals["total_outstanding"] == Decimal("1250")


def test_overdue_count_counts_only_unpaid_past_due():
    invoices = [
        inv("a", "c1", "1000", date(2025, 5, 1)),                       # unpaid, overdue
        inv("b", "c2", "250", date(2025, 6, 20)),                       # unpaid, not due yet
        inv("c", "c3", "400", date(2025, 5, 1), status="paid",
            paid_at=datetime(2025, 5, 2, 8, 0)),                        # paid, excluded
        inv("d", "c3", "700", date(2025, 5, 1), status="draft"),        # draft, excluded
    ]
    totals = compute_dues(invoices, CUSTOMERS, TODAY)["totals"]
    assert totals["overdue_count"] == 1


def test_collected_this_month_includes_this_month_and_excludes_last_month():
    invoices = [
        inv("a", "c1", "1000", date(2025, 6, 1), status="paid", paid_at=datetime(2025, 6, 4, 10, 0)),
        inv("b", "c2", "600", date(2025, 5, 1), status="paid", paid_at=datetime(2025, 5, 28, 10, 0)),
    ]
    totals = compute_dues(invoices, CUSTOMERS, TODAY)["totals"]
    assert totals["collected_this_month"] == Decimal("1000")


def test_recovered_this_month_includes_late_payment_and_excludes_on_time():
    invoices = [
        # paid this month after due date -> recovered
        inv("a", "c1", "1000", date(2025, 6, 1), status="paid", paid_at=datetime(2025, 6, 5, 10, 0)),
        # paid this month on/before due date -> not recovered
        inv("b", "c2", "600", date(2025, 6, 20), status="paid", paid_at=datetime(2025, 6, 3, 10, 0)),
    ]
    totals = compute_dues(invoices, CUSTOMERS, TODAY)["totals"]
    assert totals["recovered_this_month"] == Decimal("1000")


def test_money_fields_are_decimal():
    invoices = [inv("a", "c1", "1000", date(2025, 5, 1))]
    result = compute_dues(invoices, CUSTOMERS, TODAY)
    assert isinstance(result["rows"][0]["total_due"], Decimal)
    assert isinstance(result["totals"]["total_outstanding"], Decimal)


def test_empty_input_returns_empty_rows_and_zero_totals():
    result = compute_dues([], CUSTOMERS, TODAY)
    assert result["rows"] == []
    totals = result["totals"]
    assert totals["total_outstanding"] == Decimal("0")
    assert isinstance(totals["total_outstanding"], Decimal)
    assert totals["collected_this_month"] == Decimal("0")
    assert isinstance(totals["collected_this_month"], Decimal)
    assert totals["recovered_this_month"] == Decimal("0")
    assert isinstance(totals["recovered_this_month"], Decimal)
    assert totals["overdue_count"] == 0
    assert isinstance(totals["overdue_count"], int)
