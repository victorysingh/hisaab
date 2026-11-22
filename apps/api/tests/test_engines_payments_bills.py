from datetime import date, datetime
from copy import deepcopy
from decimal import Decimal

import pytest

from engines.payments import allocate_payment
from engines.bills import next_due_date


RECEIVED = datetime(2025, 6, 10, 12, 0, 0)


def _inv(id_, amount, due, status="sent", paid_at=None, **extra):
    return {
        "id": id_,
        "customer_id": "c1",
        "amount": Decimal(amount),
        "due_date": due,
        "status": status,
        "paid_at": paid_at,
        **extra,
    }


def test_full_payment_marks_paid_with_no_excess():
    invoices = [_inv("i1", "1000", date(2025, 6, 1))]
    result = allocate_payment(invoices, Decimal("1000"), RECEIVED)
    assert result["invoice_id"] == "i1"
    assert result["status"] == "paid"
    assert result["paid_at"] == RECEIVED
    assert result["applied_amount"] == Decimal("1000")
    assert result["unallocated"] == Decimal("0")


def test_overpayment_reports_excess_as_unallocated():
    invoices = [_inv("i1", "1000", date(2025, 6, 1))]
    result = allocate_payment(invoices, Decimal("1250"), RECEIVED)
    assert result["status"] == "paid"
    assert result["paid_at"] == RECEIVED
    assert result["applied_amount"] == Decimal("1000")
    assert result["unallocated"] == Decimal("250")


def test_partial_payment_marks_partially_paid():
    invoices = [_inv("i1", "1000", date(2025, 6, 1))]
    result = allocate_payment(invoices, Decimal("400"), RECEIVED)
    assert result["status"] == "partially_paid"
    assert result["paid_at"] is None
    assert result["applied_amount"] == Decimal("400")
    assert result["unallocated"] == Decimal("0")


def test_no_invoice_id_picks_earliest_due_date():
    invoices = [
        _inv("late", "500", date(2025, 7, 1)),
        _inv("early", "500", date(2025, 6, 1)),
    ]
    result = allocate_payment(invoices, Decimal("500"), RECEIVED)
    assert result["invoice_id"] == "early"


def test_explicit_invoice_id_overrides_older_unpaid_invoice():
    invoices = [
        _inv("old", "500", date(2025, 5, 1)),
        _inv("new", "500", date(2025, 7, 1)),
    ]
    result = allocate_payment(invoices, Decimal("500"), RECEIVED, invoice_id="new")
    assert result["invoice_id"] == "new"


def test_explicit_paid_invoice_id_raises():
    invoices = [_inv("i1", "500", date(2025, 6, 1), status="paid", paid_at=RECEIVED)]
    with pytest.raises(ValueError):
        allocate_payment(invoices, Decimal("500"), RECEIVED, invoice_id="i1")


def test_all_paid_or_draft_raises_no_unpaid():
    invoices = [
        _inv("i1", "500", date(2025, 6, 1), status="paid", paid_at=RECEIVED),
        _inv("i2", "500", date(2025, 6, 1), status="draft"),
    ]
    with pytest.raises(ValueError, match="No unpaid invoice"):
        allocate_payment(invoices, Decimal("500"), RECEIVED)


@pytest.mark.parametrize("amount", [Decimal("0"), Decimal("-1")])
def test_non_positive_amount_raises(amount):
    invoices = [_inv("i1", "500", date(2025, 6, 1))]
    with pytest.raises(ValueError):
        allocate_payment(invoices, amount, RECEIVED)


def test_inputs_not_mutated():
    invoices = [
        _inv("a", "1000", date(2025, 6, 1)),
        _inv("b", "800", date(2025, 5, 1)),
    ]
    snapshot = deepcopy(invoices)
    allocate_payment(invoices, Decimal("1500"), RECEIVED)
    assert invoices == snapshot


def test_aisha_case_pays_oldest_period_first():
    invoices = [
        _inv("inv-2025-04", "2500", date(2025, 4, 5), period="2025-04"),
        _inv("inv-2025-05", "2500", date(2025, 5, 5), period="2025-05"),
    ]
    result = allocate_payment(invoices, Decimal("2500"), RECEIVED)
    assert result["invoice_id"] == "inv-2025-04"
    assert result["status"] == "paid"


def test_next_due_date_later_this_month():
    assert next_due_date(7, date(2025, 6, 3)) == date(2025, 6, 7)


def test_next_due_date_rolls_to_next_month():
    assert next_due_date(5, date(2025, 6, 10)) == date(2025, 7, 5)


def test_next_due_date_same_day_is_today():
    assert next_due_date(5, date(2025, 6, 5)) == date(2025, 6, 5)


def test_next_due_date_rolls_over_year_end():
    assert next_due_date(3, date(2025, 12, 20)) == date(2026, 1, 3)


@pytest.mark.parametrize("due_day", [0, 29, 31])
def test_next_due_date_rejects_invalid_day(due_day):
    with pytest.raises(ValueError):
        next_due_date(due_day, date(2025, 6, 1))
