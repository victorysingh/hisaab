"""Tests for engines/forecast.py - pure, offline, deterministic (today is passed in)."""

import time
from datetime import date, timedelta
from decimal import Decimal

import pytest

from engines.forecast import build_forecast, delay_stats, chronic_customers, fmt_rs, what_if

TODAY = date(2026, 11, 22)


def cust(cid, name, fee="2500", status="active", due_day=5):
    return {"id": cid, "name": name, "monthly_fee": fee, "due_day": due_day, "status": status}


def inv(cid, period, amount="2500", status="paid", paid_late_days=0, due_day=5):
    y, m = map(int, period.split("-"))
    due = date(y, m, due_day)
    paid_at = (due + timedelta(days=paid_late_days)).isoformat() if status == "paid" else None
    return {"id": f"{cid}-{period}", "customer_id": cid, "period": period, "amount": amount,
            "due_date": due.isoformat(), "status": status, "paid_at": paid_at}


RENT = {"id": "b1", "name": "Rent", "amount": "12000", "due_day": 1, "recurrence": "monthly"}
SALARY = {"id": "b2", "name": "Assistant salary", "amount": "8000", "due_day": 7, "recurrence": "monthly"}


def kwargs(**over):
    base = dict(today=TODAY, days=60, start_balance="50000", safety_buffer="0",
                customers=[], invoices=[], bills=[])
    base.update(over)
    return base


def by_date(result, d):
    return next(row for row in result["days"] if row["date"] == d)


# ---------- helpers ----------

def test_fmt_rs_indian_grouping():
    assert fmt_rs(Decimal("120000")) == "Rs 1,20,000"
    assert fmt_rs(Decimal("8400")) == "Rs 8,400"
    assert fmt_rs(Decimal("950")) == "Rs 950"


def test_delay_stats_and_new_customer_default():
    invoices = [inv("k", f"2026-0{m}", paid_late_days=d) for m, d in [(6, 10), (7, 18), (8, 20), (9, 25)]]
    stats = delay_stats(invoices)
    p25, p50, p75 = stats["k"]
    assert p25 <= p50 <= p75
    assert p50 >= 18
    assert "nobody" not in stats  # customers with <2 paid invoices get the default in the engine


def test_chronic_customer_detection():
    invoices = [inv("p", f"2026-0{m}", status="sent") for m in (6, 7, 8)]
    assert chronic_customers(invoices, TODAY) == {"p"}
    assert chronic_customers(invoices[:2], TODAY) == set()


# ---------- the 5 behaviours from the brief ----------

def test_no_bills_and_all_paid_means_no_shortfall():
    customers = [cust("a", "Aisha Khan")]
    invoices = [inv("a", "2026-10"), inv("a", "2026-11")]
    result = build_forecast(**kwargs(customers=customers, invoices=invoices))
    assert result["shortfall"] is None
    assert result["causes"] == []
    assert len(result["days"]) == 61


def test_rent_larger_than_balance_with_late_fees_gives_shortfall_on_the_1st():
    customers = [cust("k", "Kabir Mehta"), cust("p", "Parth Kale", fee="3000")]
    invoices = (
        [inv("k", f"2026-0{m}", paid_late_days=20) for m in (6, 7, 8, 9)]
        + [inv("k", "2026-10", paid_late_days=20), inv("k", "2026-11", status="overdue")]
        + [inv("p", f"2026-{m:02d}", amount="3000", status="overdue") for m in (8, 9, 10, 11)]
    )
    result = build_forecast(**kwargs(start_balance="5000", customers=customers, invoices=invoices, bills=[RENT]))
    assert result["shortfall"] is not None
    assert result["shortfall"]["date"] == "2026-12-01"
    assert result["shortfall"]["amount"] > 0
    labels = [c["label"] for c in result["causes"]]
    assert "Rent" in labels
    assert any(l.startswith("Parth Kale") for l in labels)  # chronic, not expected in likely case
    assert len(result["causes"]) <= 5


def test_best_ge_likely_ge_worst_every_day():
    customers = [cust(c, c.upper()) for c in "abcdef"]
    invoices = []
    for i, c in enumerate("abcdef"):
        invoices += [inv(c, f"2026-0{m}", paid_late_days=(i * 4 + m) % 15) for m in (6, 7, 8, 9)]
        invoices.append(inv(c, "2026-11", status="overdue" if i % 2 else "paid", paid_late_days=2))
    result = build_forecast(**kwargs(days=90, start_balance="3000", customers=customers, invoices=invoices,
                                     bills=[RENT, SALARY]))
    for row in result["days"]:
        assert row["best"] >= row["likely"] >= row["worst"], row


def test_what_if_delay_moves_likely_line_down_in_between():
    customers = [cust("k", "Kabir Mehta")]
    invoices = [inv("k", f"2026-{m:02d}", paid_late_days=2) for m in (6, 7, 8, 9, 10, 11)]
    base_kwargs = kwargs(start_balance="1000", customers=customers, invoices=invoices, bills=[RENT])
    result = what_if(baseline_kwargs=base_kwargs, changes=[{"type": "delay", "customer_id": "k", "days": 15}])
    base = result["baseline"]
    # Kabir's December fee (due 5 Dec, usually +2) arrives ~7 Dec in baseline, ~22 Dec with the delay
    assert by_date(result, "2026-12-10")["likely"] < by_date(base, "2026-12-10")["likely"]
    assert by_date(result, "2026-12-31")["likely"] == by_date(base, "2026-12-31")["likely"]


def test_ninety_day_forecast_under_500ms_on_seed_sized_data():
    customers = [cust(f"c{i}", f"Student {i}", fee="3000" if i % 2 else "2500") for i in range(40)]
    invoices = []
    for i in range(40):
        for m in (6, 7, 8, 9, 10, 11):
            invoices.append(inv(f"c{i}", f"2026-{m:02d}", status="overdue" if (i < 2 or (m == 11 and i < 6)) else "paid",
                                paid_late_days=(i * 7 + m) % 25))
    bills = [RENT, SALARY,
             {"id": "b3", "name": "Electricity", "amount": "1800", "due_day": 15, "recurrence": "monthly"},
             {"id": "b4", "name": "Wi-Fi", "amount": "900", "due_day": 10, "recurrence": "monthly"}]
    started = time.perf_counter()
    result = build_forecast(**kwargs(days=90, start_balance="18000", customers=customers, invoices=invoices, bills=bills))
    assert time.perf_counter() - started < 0.5
    assert len(result["days"]) == 91


# ---------- what-if variants and explanations ----------

def test_what_if_new_one_off_bill_creates_shortfall():
    customers = [cust("a", "Aisha Khan")]
    invoices = [inv("a", "2026-10"), inv("a", "2026-11")]
    base_kwargs = kwargs(start_balance="10000", customers=customers, invoices=invoices)
    result = what_if(baseline_kwargs=base_kwargs,
                     changes=[{"type": "new_bill", "name": "AC repair", "amount": "15000", "date": "2026-11-30"}])
    assert result["baseline"]["shortfall"] is None
    assert result["shortfall"] == {"date": "2026-11-30", "amount": Decimal("5000")}
    assert result["causes"][0]["label"] == "AC repair"


def test_what_if_drop_removes_future_fees():
    customers = [cust("a", "Aisha Khan"), cust("b", "Rohan Sharma", fee="3000")]
    invoices = [inv("a", "2026-11"), inv("b", "2026-11", amount="3000")]
    base_kwargs = kwargs(customers=customers, invoices=invoices)
    result = what_if(baseline_kwargs=base_kwargs,
                     changes=[{"type": "drop", "customer_ids": ["b"], "from_period": "2026-12"}])
    end = result["days"][-1]["likely"]
    base_end = result["baseline"]["days"][-1]["likely"]
    assert base_end - end == Decimal("6000")  # Rohan's Dec + Jan fees gone


def test_assumptions_are_plain_sentences():
    customers = [cust("k", "Kabir Mehta")]
    invoices = [inv("k", f"2026-{m:02d}", paid_late_days=18) for m in (6, 7, 8, 9, 10, 11)]
    result = build_forecast(**kwargs(start_balance="18000", customers=customers, invoices=invoices, bills=[RENT]))
    text = " | ".join(result["assumptions"])
    assert "Starting cash Rs 18,000" in text
    assert "Rent Rs 12,000 on the 1st every month" in text
    assert "Kabir Mehta usually pays 18 days late" in text


def test_days_must_be_30_60_or_90():
    with pytest.raises(ValueError):
        build_forecast(**kwargs(days=45))