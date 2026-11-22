"""Match a parsed payment to the most likely unpaid invoice.

match_payment(event, invoices, customers, aliases, received_on, delay_stats) -> dict
  {status: matched|needs_review|unmatched, invoice_id, customer_id, confidence, candidates: [...]}

Scoring out of 100:
  amount: exact 40, within Rs 50 25, a multiple of the monthly fee 20
  payer:  UPI id or payer name already confirmed for that student 40,
          else fuzzy name match against student or parent name, up to 30
  timing: inside that student's usual payment window 20, otherwise 10
matched if top >= 90 and at least 15 ahead of any other student; needs_review if top >= 40.
Pure function.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from decimal import Decimal
from difflib import SequenceMatcher

AUTO_MATCH = 90
AUTO_LEAD = 15
REVIEW_MIN = 40
WINDOW_BEFORE_DUE = 60   # candidates: due up to 60 days before the payment ...
WINDOW_AFTER_PAYMENT = 10  # ... or up to 10 days after it (early payers)
TITLES = {"mr", "mrs", "ms", "miss", "shri", "smt", "dr", "master", "kumari"}


def _d(value) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _money(value) -> Decimal:
    return Decimal(str(value or 0))


def normalise(name: str | None) -> str:
    words = re.sub(r"[^a-z ]+", " ", (name or "").lower()).split()
    return " ".join(w for w in words if w not in TITLES)


def name_score(payer: str | None, *targets: str | None) -> int:
    """0-30. Mix of whole-string similarity and shared words (first name or surname)."""
    p = normalise(payer)
    if not p:
        return 0
    best = 0.0
    p_tokens = {t for t in p.split() if len(t) >= 2}
    for target in targets:
        t = normalise(target)
        if not t:
            continue
        ratio = SequenceMatcher(None, p, t).ratio()
        t_tokens = set(t.split())
        shared = len(p_tokens & t_tokens) / max(1, len(p_tokens)) if p_tokens else 0
        initials = any(len(tok) == 1 and any(w.startswith(tok) for w in t_tokens) for tok in p.split())
        token_score = shared + (0.15 if initials and shared else 0)
        best = max(best, ratio, min(1.0, token_score))
    return round(30 * best)


def match_payment(event: dict, invoices: list[dict], customers: list[dict], aliases: list[dict],
                  received_on: date, delay_stats: dict | None = None) -> dict:
    amount = _money(event.get("amount"))
    upi_id = (event.get("upi_id") or "").lower()
    payer = event.get("payer_text")
    stats = delay_stats or {}
    by_id = {c["id"]: c for c in customers}

    alias_hits: set[str] = set()
    for a in aliases:
        value = (a.get("alias_value") or "").lower()
        if not value:
            continue
        if (a.get("alias_type") == "upi_id" and upi_id and value == upi_id) or (
            a.get("alias_type") == "payer_name" and payer and normalise(value) == normalise(payer)
        ):
            alias_hits.add(a["customer_id"])

    lo = received_on - timedelta(days=WINDOW_BEFORE_DUE)
    hi = received_on + timedelta(days=WINDOW_AFTER_PAYMENT)
    candidates = []
    for inv in invoices:
        if inv.get("status") == "paid":
            continue
        due = _d(inv.get("due_date"))
        if due is None or not (lo <= due <= hi):
            continue
        cust = by_id.get(inv["customer_id"], {})
        inv_amount = _money(inv.get("amount"))
        fee = _money(cust.get("monthly_fee")) or inv_amount

        if amount == inv_amount:
            amount_pts = 40
        elif abs(amount - inv_amount) <= 50:
            amount_pts = 25
        elif fee > 0 and amount > inv_amount and amount % fee == 0:
            amount_pts = 20
        else:
            amount_pts = 0

        if inv["customer_id"] in alias_hits:
            payer_pts = 40
        else:
            payer_pts = name_score(payer, cust.get("name"), cust.get("guardian_name"))

        p75 = stats.get(inv["customer_id"], (0, 3, 7))[2]
        timing_pts = 20 if due - timedelta(days=5) <= received_on <= due + timedelta(days=max(p75, 7) + 3) else 10

        score = min(100, amount_pts + payer_pts + timing_pts)
        candidates.append({
            "invoice_id": inv["id"],
            "customer_id": inv["customer_id"],
            "customer_name": cust.get("name", "Student"),
            "period": inv.get("period"),
            "amount": inv_amount,
            "due_date": due.isoformat(),
            "score": score,
        })

    # best invoice per student: highest score, then oldest due date
    candidates.sort(key=lambda c: (-c["score"], c["due_date"]))
    best_per_customer: dict[str, dict] = {}
    for c in candidates:
        best_per_customer.setdefault(c["customer_id"], c)
    ranked = sorted(best_per_customer.values(), key=lambda c: (-c["score"], c["due_date"]))

    if not ranked:
        return {"status": "unmatched", "invoice_id": None, "customer_id": None, "confidence": 0, "candidates": []}

    top = ranked[0]
    runner_up = ranked[1]["score"] if len(ranked) > 1 else 0
    if top["score"] >= AUTO_MATCH and top["score"] - runner_up >= AUTO_LEAD:
        status = "matched"
    elif top["score"] >= REVIEW_MIN:
        status = "needs_review"
    else:
        status = "unmatched"
    return {
        "status": status,
        "invoice_id": top["invoice_id"] if status == "matched" else None,
        "customer_id": top["customer_id"] if status == "matched" else None,
        "confidence": top["score"],
        "candidates": ranked[:3],
    }
