"""Parse Indian bank / UPI credit SMS into payment events.

parse_sms(text) -> dict | None
  {amount: Decimal, payer_text: str|None, upi_id: str|None, upi_ref: str|None, is_credit: True}
Returns None for debits, OTPs, promotions and anything without a credited amount.
Pure function: no network, no LLM.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

AMOUNT_RE = re.compile(r"(?:rs\.?|inr|₹)\s*([\d,]+(?:\.\d{1,2})?)", re.I)
CREDIT_RE = re.compile(r"\b(credited|received|deposited|credit(?:ed)? to|cr\b)", re.I)
DEBIT_RE = re.compile(r"\b(debited|spent|withdrawn|paid to|sent to|debit)\b", re.I)
OTP_RE = re.compile(r"\b(otp|one[- ]time password|verification code)\b", re.I)
PROMO_RE = re.compile(r"\b(offer|cashback|win|won|pre-?approved|loan of|discount|voucher|reward points)\b", re.I)
UPI_ID_RE = re.compile(r"\b([a-z0-9][a-z0-9._-]{1,63})@([a-z][a-z0-9]{1,30})\b", re.I)
REF_RE = re.compile(
    r"(?:upi\s*ref(?:erence)?|ref(?:erence)?|rrn|txn\s*id|transaction\s*id)\.?\s*(?:no\.?|number|id)?\s*[:#.-]?\s*(\d{9,14})",
    re.I,
)
INFO_RE = re.compile(r"UPI/(?:CR|P2A|P2P)?/?(\d{9,14})/([A-Za-z][A-Za-z .]{1,40}?)/", re.I)
FROM_RE = re.compile(
    r"\b(?:from|by)\s+(?!vpa\b|a/c\b|ac\b|upi\b|rs\b|inr\b|linked\b|your\b|cash\b|neft\b|imps\b)([A-Za-z][A-Za-z.]*(?:\s+[A-Za-z][A-Za-z.]*){0,3})",
    re.I,
)
STOP_WORDS = {"via", "on", "upi", "ref", "info", "avl", "avbl", "bal", "balance", "your", "a/c", "ac", "to",
              "vpa", "in", "the", "at", "for", "not", "you", "call", "if", "rs", "inr", "linked", "neft", "imps"}


def _amount(text: str) -> Decimal | None:
    for match in AMOUNT_RE.finditer(text):
        # skip "Avl Bal Rs ..." style balances
        before = text[max(0, match.start() - 12):match.start()].lower()
        if "bal" in before:
            continue
        try:
            value = Decimal(match.group(1).replace(",", ""))
        except InvalidOperation:
            continue
        if value > 0:
            return value
    return None


def _clean_name(raw: str | None) -> str | None:
    if not raw:
        return None
    words = []
    for w in raw.replace(".", " ").split():
        if w.lower() in STOP_WORDS:
            break
        words.append(w)
    name = " ".join(words).strip()
    return name.title() if len(name) >= 2 else None


def parse_sms(text: str) -> dict | None:
    if not text or OTP_RE.search(text):
        return None
    credit = CREDIT_RE.search(text)
    debit = DEBIT_RE.search(text)
    if not credit or (debit and debit.start() < credit.start()):
        return None
    if PROMO_RE.search(text) and not re.search(r"\b(a/c|acct|account)\b", text, re.I):
        return None
    amount = _amount(text)
    if amount is None:
        return None

    upi_ref = None
    payer = None
    info = INFO_RE.search(text)
    if info:
        upi_ref = info.group(1)
        payer = _clean_name(info.group(2))
    ref = REF_RE.search(text)
    if ref and not upi_ref:
        upi_ref = ref.group(1)

    upi_id = None
    vpa = UPI_ID_RE.search(text)
    if vpa:
        upi_id = f"{vpa.group(1)}@{vpa.group(2)}".lower()

    if payer is None:
        m = FROM_RE.search(text)
        if m:
            payer = _clean_name(m.group(1))
    if payer is None and upi_id:
        local = upi_id.split("@")[0]
        payer = _clean_name(re.sub(r"[._-]+", " ", re.sub(r"\d+", " ", local)))

    return {"amount": amount, "payer_text": payer, "upi_id": upi_id, "upi_ref": upi_ref, "is_credit": True}
