"""Cash forecast engine for Hisaab.

Pure functions: no database, no network, no date.today(). The router loads data,
passes it in with `today`, and serialises the result. All money is Decimal.

Inputs are plain dicts as they come from Supabase:
  customers: {id, name, monthly_fee, due_day, status}
  invoices:  {id, customer_id, period 'YYYY-MM', amount, due_date, status, paid_at}
  bills:     {id, name, amount, due_day, recurrence 'monthly'|'once', next_due_date}
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Iterable

NEW_CUSTOMER_DELAYS = (0, 3, 7)  # p25, median, p75 for customers with < 2 paid invoices
OVERDUE_FLOOR_DAYS = 2           # an expected date already in the past moves to today + 2
CHRONIC_MIN_INVOICES = 3         # this many invoices ...
CHRONIC_DAYS_LATE = 30           # ... more than this many days late = chronic non-payer
MAX_CAUSES = 5
SCENARIOS = ("best", "likely", "worst")
SCENARIO_INDEX = {"best": 0, "likely": 1, "worst": 2}
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# ---------- small helpers ----------

def to_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def to_money(value: Any) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    return Decimal(str(value))


def safe_date(year: int, month: int, day: int) -> date:
    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(max(day, 1), last))


def add_months(year: int, month: int, n: int) -> tuple[int, int]:
    idx = year * 12 + (month - 1) + n
    return idx // 12, idx % 12 + 1


def period_of(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def month_label(period: str) -> str:
    y, m = period.split("-")
    return f"{MONTHS[int(m) - 1]} {y}"


def fmt_rs(amount: Decimal) -> str:
    """Indian digit grouping: 120000 -> 'Rs 1,20,000'."""
    n = int(amount.quantize(Decimal("1")))
    sign = "-" if n < 0 else ""
    s = str(abs(n))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        s = ",".join(groups) + "," + tail
    return f"Rs {sign}{s}"


def percentile(sorted_values: list[int], p: float) -> int:
    """Nearest-rank percentile on an already sorted list."""
    if not sorted_values:
        return 0
    k = max(0, min(len(sorted_values) - 1, round(p * (len(sorted_values) - 1))))
    return sorted_values[k]


def is_paid(inv: dict) -> bool:
    return inv.get("status") == "paid"


# ---------- building blocks ----------

def delay_stats(invoices: Iterable[dict]) -> dict[str, tuple[int, int, int]]:
    """Per customer (p25, median, p75) of paid_at - due_date in days (never below 0)."""
    delays: dict[str, list[int]] = {}
    for inv in invoices:
        if not is_paid(inv):
            continue
        due, paid = to_date(inv.get("due_date")), to_date(inv.get("paid_at"))
        if due is None or paid is None:
            continue
        delays.setdefault(inv["customer_id"], []).append(max(0, (paid - due).days))
    stats: dict[str, tuple[int, int, int]] = {}
    for cid, values in delays.items():
        if len(values) < 2:
            continue
        values.sort()
        stats[cid] = (percentile(values, 0.25), percentile(values, 0.5), percentile(values, 0.75))
    return stats


def chronic_customers(invoices: Iterable[dict], today: date) -> set[str]:
    counts: dict[str, int] = {}
    for inv in invoices:
        if is_paid(inv):
            continue
        due = to_date(inv.get("due_date"))
        if due is not None and (today - due).days > CHRONIC_DAYS_LATE:
            counts[inv["customer_id"]] = counts.get(inv["customer_id"], 0) + 1
    return {cid for cid, n in counts.items() if n >= CHRONIC_MIN_INVOICES}


def future_invoices(customers: Iterable[dict], invoices: Iterable[dict], today: date, end: date) -> list[dict]:
    """Invoices that will be raised in the horizon for active customers (not yet in the table)."""
    existing = {(inv["customer_id"], inv.get("period")) for inv in invoices}
    result = []
    for c in customers:
        if c.get("status", "active") != "active":
            continue
        due_day = int(c.get("due_day") or 5)
        y, m = today.year, today.month
        for i in range(0, 5):
            yy, mm = add_months(y, m, i)
            due = safe_date(yy, mm, due_day)
            if due <= today or due > end:
                continue
            period = f"{yy:04d}-{mm:02d}"
            if (c["id"], period) in existing:
                continue
            result.append({
                "id": f"future-{c['id']}-{period}",
                "customer_id": c["id"],
                "period": period,
                "amount": to_money(c.get("monthly_fee")),
                "due_date": due,
                "status": "future",
                "paid_at": None,
            })
    return result


def bill_events(bills: Iterable[dict], today: date, end: date) -> list[dict]:
    """Each bill occurrence with a date in (today, end]."""
    events = []
    for b in bills:
        amount = to_money(b.get("amount"))
        if b.get("recurrence", "monthly") == "once":
            d = to_date(b.get("next_due_date") or b.get("date"))
            if d is not None and today < d <= end:
                events.append({"name": b["name"], "amount": amount, "date": d, "recurrence": "once"})
            continue
        due_day = int(b.get("due_day") or 1)
        for i in range(0, 5):
            yy, mm = add_months(today.year, today.month, i)
            d = safe_date(yy, mm, due_day)
            if today < d <= end:
                events.append({"name": b["name"], "amount": amount, "date": d, "recurrence": "monthly",
                               "due_day": due_day})
    return events


# ---------- what-if ----------

def apply_changes(customers: list[dict], invoices: list[dict], bills: list[dict],
                  changes: list[dict] | None) -> tuple[list[dict], list[dict], list[dict], dict[str, int]]:
    """Return copies of the inputs with scenario changes applied, plus extra delay days per customer."""
    customers = [dict(c) for c in customers]
    invoices = [dict(i) for i in invoices]
    bills = [dict(b) for b in bills]
    extra_delay: dict[str, int] = {}
    for ch in changes or []:
        kind = ch.get("type")
        if kind == "delay":
            cid = ch["customer_id"]
            extra_delay[cid] = extra_delay.get(cid, 0) + int(ch.get("days", 0))
        elif kind == "drop":
            ids = set(ch.get("customer_ids") or [])
            from_period = ch.get("from_period") or "0000-00"
            invoices = [i for i in invoices
                        if not (i["customer_id"] in ids and not is_paid(i) and i.get("period", "") >= from_period)]
            for c in customers:
                if c["id"] in ids:
                    c["status"] = "left"
        elif kind == "new_bill":
            bills.append({
                "id": f"whatif-bill-{len(bills)}",
                "name": ch.get("name", "New bill"),
                "amount": ch.get("amount", 0),
                "recurrence": ch.get("recurrence", "once"),
                "next_due_date": ch.get("date"),
                "due_day": to_date(ch.get("date")).day if ch.get("date") else 1,
            })
        elif kind == "new_customer":
            customers.append({
                "id": f"whatif-customer-{len(customers)}",
                "name": ch.get("name", "New student"),
                "monthly_fee": ch.get("monthly_fee", 0),
                "due_day": ch.get("due_day", 5),
                "status": "active",
                "start_period": ch.get("start_period"),
            })
    return customers, invoices, bills, extra_delay


# ---------- main entry point ----------

def build_forecast(*, today: date, days: int, start_balance: Any, safety_buffer: Any,
                   customers: list[dict], invoices: list[dict], bills: list[dict],
                   changes: list[dict] | None = None) -> dict:
    if days not in (30, 60, 90):
        raise ValueError("days must be 30, 60 or 90")
    end = today + timedelta(days=days)
    start = to_money(start_balance)
    buffer = to_money(safety_buffer)

    customers, invoices, bills, extra_delay = apply_changes(customers, invoices, bills, changes)
    names = {c["id"]: c.get("name", "Student") for c in customers}
    stats = delay_stats(invoices)
    chronic = chronic_customers(invoices, today)
    status_by_id = {c["id"]: c.get("status", "active") for c in customers}

    future = future_invoices(customers, invoices, today, end)
    # new customers from what-if only start from their start_period
    starts = {c["id"]: c.get("start_period") for c in customers if c.get("start_period")}
    future = [f for f in future if not starts.get(f["customer_id"]) or f["period"] >= starts[f["customer_id"]]]

    open_invoices = [i for i in invoices if not is_paid(i)] + future

    # day -> [best, likely, worst] net change
    deltas: dict[date, list[Decimal]] = {}
    expected_likely: dict[str, date | None] = {}

    def add(d: date, idx: int, amount: Decimal) -> None:
        if today < d <= end:
            deltas.setdefault(d, [Decimal("0"), Decimal("0"), Decimal("0")])[idx] += amount

    for inv in open_invoices:
        cid = inv["customer_id"]
        due = to_date(inv.get("due_date"))
        if due is None:
            continue
        amount = to_money(inv.get("amount"))
        p25, p50, p75 = stats.get(cid, NEW_CUSTOMER_DELAYS)
        unreliable = cid in chronic or status_by_id.get(cid) == "left"
        for scenario, delay in zip(SCENARIOS, (p25, p50, p75)):
            if unreliable and scenario != "best":
                if scenario == "likely":
                    expected_likely[inv["id"]] = None
                continue
            expected = due + timedelta(days=delay + extra_delay.get(cid, 0))
            floor = today + timedelta(days=OVERDUE_FLOOR_DAYS)
            if expected < floor and due <= today:
                expected = floor + timedelta(days=extra_delay.get(cid, 0))
            if scenario == "likely":
                expected_likely[inv["id"]] = expected
            add(expected, SCENARIO_INDEX[scenario], amount)

    events = bill_events(bills, today, end)
    for ev in events:
        for idx in range(3):
            add(ev["date"], idx, -ev["amount"])

    # walk day by day
    balances = [start, start, start]
    series = [{"date": today.isoformat(), "best": start, "likely": start, "worst": start}]
    shortfall = None
    for n in range(1, days + 1):
        d = today + timedelta(days=n)
        change = deltas.get(d)
        if change:
            balances = [balances[k] + change[k] for k in range(3)]
        series.append({"date": d.isoformat(), "best": balances[0], "likely": balances[1], "worst": balances[2]})
        if shortfall is None and balances[1] < buffer:
            shortfall = {"date": d.isoformat(), "amount": buffer - balances[1]}
    if shortfall is None and start < buffer:
        shortfall = {"date": today.isoformat(), "amount": buffer - start}

    causes = _causes(shortfall, invoices, expected_likely, events, names, today)
    assumptions = _assumptions(start, stats, chronic, names, events, status_by_id)

    return {
        "today": today.isoformat(),
        "days_ahead": days,
        "start_balance": start,
        "safety_buffer": buffer,
        "days": series,
        "shortfall": shortfall,
        "causes": causes,
        "assumptions": assumptions,
    }


def what_if(*, baseline_kwargs: dict, changes: list[dict]) -> dict:
    """Run the forecast twice: as-is and with changes. Same inputs as build_forecast."""
    base = build_forecast(**baseline_kwargs)
    scenario = build_forecast(**baseline_kwargs, changes=changes)
    scenario["baseline"] = base
    return scenario


# ---------- explanations ----------

def _causes(shortfall: dict | None, invoices: list[dict], expected_likely: dict[str, date | None],
            events: list[dict], names: dict[str, str], today: date) -> list[dict]:
    if shortfall is None:
        return []
    sdate = to_date(shortfall["date"])
    causes = []
    # Overdue fees not expected before the shortfall, grouped per student so one person = one line.
    owed: dict[str, dict] = {}
    for inv in invoices:
        if is_paid(inv):
            continue
        due = to_date(inv.get("due_date"))
        if due is None or due > today:
            continue  # only invoices already overdue
        exp = expected_likely.get(inv["id"], "missing")
        if exp is None or (isinstance(exp, date) and exp > sdate):
            g = owed.setdefault(inv["customer_id"], {"amount": Decimal("0"), "months": [], "oldest": due})
            g["amount"] += to_money(inv.get("amount"))
            g["months"].append(inv.get("period") or "")
            g["oldest"] = min(g["oldest"], due)
    for cid, g in owed.items():
        name = names.get(cid, "Student")
        n = len(g["months"])
        label = f"{name} - {n} months unpaid" if n > 1 else (
            f"{name} - {month_label(g['months'][0])} fees" if g["months"][0] else name)
        causes.append({"type": "overdue_invoice", "label": label, "amount": g["amount"], "date": g["oldest"].isoformat()})
    for ev in events:
        if ev["date"] <= sdate:
            causes.append({"type": "bill", "label": ev["name"], "amount": ev["amount"], "date": ev["date"].isoformat()})
    causes.sort(key=lambda c: c["amount"], reverse=True)
    return causes[:MAX_CAUSES]


def _ordinal(n: int) -> str:
    suffix = "th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _assumptions(start: Decimal, stats: dict, chronic: set[str], names: dict[str, str],
                 events: list[dict], status_by_id: dict[str, str]) -> list[str]:
    lines = [f"Starting cash {fmt_rs(start)}"]
    seen_bills = set()
    for ev in sorted(events, key=lambda e: e["date"]):
        if ev["name"] in seen_bills:
            continue
        seen_bills.add(ev["name"])
        if ev["recurrence"] == "monthly":
            lines.append(f"{ev['name']} {fmt_rs(ev['amount'])} on the {_ordinal(ev['due_day'])} every month")
        else:
            lines.append(f"{ev['name']} {fmt_rs(ev['amount'])} on {ev['date'].day} {MONTHS[ev['date'].month - 1]}")
    late = sorted(((s[1], cid) for cid, s in stats.items() if s[1] >= 7 and cid not in chronic), reverse=True)[:3]
    for median_days, cid in late:
        lines.append(f"{names.get(cid, 'A student')} usually pays {median_days} days late")
    for cid in sorted(chronic, key=lambda c: names.get(c, "")):
        if status_by_id.get(cid) != "left":
            lines.append(f"{names.get(cid, 'A student')} not counted in likely and worst cases (3+ months unpaid)")
    lines.append("New students assumed to pay 0-7 days after the due date")
    return lines
