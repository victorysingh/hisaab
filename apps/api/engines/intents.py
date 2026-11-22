"""Rule-based command understanding for the voice agent (English + Hinglish).

parse_command(text, customers, today) -> {"intent": str, "args": dict}
Intents: dues, forecast, chase, what_if, record_payment, add_customers, help.
Pure function. The same interface can later be backed by an LLM with tool calling.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from difflib import SequenceMatcher

NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30,
    "ek": 1, "teen": 3, "char": 4, "paanch": 5, "das": 10, "pandrah": 15, "bees": 20, "tees": 30,
}
MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}

WHAT_IF = ("what if", "what happens if", "suppose", "agar", "if ")
LATE = ("late", "delay", "der ", "der se", "baad mein")
LEAVE = ("leave", "leaves", "left", "stop", "stops", "quit", "quits", "chhod", "drop", "drops")
EXPENSE = ("spend", "buy", "expense", "kharcha", "purchase", "repair", "bill of", "pay for")
ADD = ("new student", "new students", "add student", "add students", "naya student", "naye student", "admission")
PAID = ("paid", "pay ", "gave", "diye", "de diye", "de diya", "mila", "received", "jama")
CHASE = ("chase", "remind", "follow up", "follow-up", "kisko", "who should i call", "who should i ask", "call whom")
FORECAST = ("rent", "short", "forecast", "manage", "enough", "next month", "cash", "balance", "future",
            "kiraya", "paisa", "afford", "salary")
DUES = ("owe", "owes", "pending", "due", "hasn't paid", "haven't paid", "not paid", "baaki", "baki", "udhaar",
        "outstanding", "kaun", "who has not")
NAME_STOP = {"and", "aur", "each", "every", "month", "monthly", "rs", "rupees", "fee", "fees", "due", "on", "the",
             "from", "with", "student", "students", "new", "add", "naya", "naye", "of", "per", "for", "is", "are"}


def _norm(text: str) -> str:
    t = text.lower().replace("₹", " rs ").replace("rupees", " rs ").replace("rupaye", " rs ")
    t = re.sub(r"(\d),(\d)", r"\1\2", t)          # 2,500 -> 2500
    t = re.sub(r"(\d)\s*k\b", r"\g<1>000", t)       # 3k -> 3000
    for word, n in NUMBER_WORDS.items():
        t = re.sub(rf"\b{word}\b", str(n), t)
    # "2 thousand 5 hundred" / "2 hazaar 5 sau" -> 2500 ; "5 hundred" -> 500 ; "2.5 thousand" -> 2500
    t = re.sub(r"\b(\d+(?:\.\d+)?)\s*(?:thousand|hazaar|hazar)(?:\s*(?:and\s*)?(\d+)\s*(?:hundred|sau))?\b",
               lambda m: str(int(float(m.group(1)) * 1000 + (int(m.group(2)) * 100 if m.group(2) else 0))), t)
    t = re.sub(r"\b(\d+)\s*(?:hundred|sau)\b", lambda m: str(int(m.group(1)) * 100), t)
    return re.sub(r"\s+", " ", t).strip()


def _has(t: str, words) -> bool:
    return any(w in t for w in words)


def _amounts(t: str) -> list[int]:
    return [int(float(x)) for x in re.findall(r"\b\d+(?:\.\d+)?\b", t) if float(x) >= 100]


def _days(t: str, default: int = 15) -> int:
    m = re.search(r"\b(\d{1,3})\s*(?:day|days|din|dino|dinon)\b", t)
    if m:
        return int(m.group(1))
    if "week" in t or "hafta" in t:
        return 7
    if "month" in t or "mahina" in t:
        return 30
    return default


def find_customers(t: str, customers: list[dict]) -> list[dict]:
    """Customers mentioned in the text, in order of appearance. Full names win over first names."""
    tokens = re.findall(r"[a-z]+", t)
    found: list[tuple[int, dict]] = []
    seen: set[str] = set()
    for c in customers:
        if c.get("status", "active") == "left":
            continue
        full = c["name"].lower()
        pos = t.find(full)
        if pos >= 0 and c["id"] not in seen:
            found.append((pos, c))
            seen.add(c["id"])
    by_first: dict[str, list[dict]] = {}
    for c in customers:
        if c.get("status", "active") != "left":
            by_first.setdefault(c["name"].split()[0].lower(), []).append(c)
    for i, tok in enumerate(tokens):
        if len(tok) < 3 or tok in NAME_STOP:
            continue
        match = by_first.get(tok)
        if not match:
            best, best_ratio = None, 0.0
            for first in by_first:
                r = SequenceMatcher(None, tok, first).ratio()
                if r > best_ratio:
                    best, best_ratio = first, r
            if best and (best_ratio >= 0.8 or (len(tok) >= 4 and best_ratio >= 0.7)):
                match = by_first[best]
        if match and match[0]["id"] not in seen:
            pos = t.find(tok)
            found.append((pos, match[0]))
            seen.add(match[0]["id"])
    return [c for _, c in sorted(found, key=lambda x: x[0])]


def _expense_date(t: str, today: date) -> date:
    m = re.search(r"\bon\s+(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]{3})", t)
    if m and m.group(2)[:3] in MONTHS:
        month = MONTHS[m.group(2)[:3]]
        year = today.year + (1 if month < today.month else 0)
        try:
            return date(year, month, int(m.group(1)))
        except ValueError:
            pass
    if "tomorrow" in t or "kal" in t:
        return today + timedelta(days=1)
    if "next week" in t or "agle hafte" in t:
        return today + timedelta(days=7)
    return today + timedelta(days=5)


def _expense_name(t: str) -> str:
    m = re.search(r"\b(?:buy|purchase|for|on)\s+(?:a|an|the|new|naya)?\s*([a-z]+(?:\s+[a-z]+)?)", t)
    if m:
        words = [w for w in m.group(1).split() if not w.isdigit() and w not in NAME_STOP and w != "rs"]
        if words:
            return " ".join(words).capitalize()
    return "One-off expense"


def _new_student_names(t: str) -> list[str]:
    m = re.search(r"(?:students?|admission)\s+(.*?)(?=\d|$)", t)
    segment = m.group(1) if m else ""
    parts = re.split(r",|\band\b|\baur\b", segment)
    names = []
    for p in parts:
        words = [w for w in re.findall(r"[a-z]+", p) if w not in NAME_STOP]
        if words:
            names.append(" ".join(w.capitalize() for w in words[:2]))
    return names


def parse_command(text: str, customers: list[dict], today: date) -> dict:
    t = _norm(text)
    if not t:
        return {"intent": "help", "args": {}}
    people = find_customers(t, customers)
    amounts = _amounts(t)

    if _has(t, WHAT_IF) or (t.startswith("if") and (people or amounts)):
        if _has(t, LATE) and people:
            return {"intent": "what_if", "args": {"changes": [
                {"type": "delay", "customer_id": c["id"], "days": _days(t)} for c in people
            ], "names": [c["name"] for c in people]}}
        if _has(t, LEAVE) and people:
            return {"intent": "what_if", "args": {"changes": [
                {"type": "drop", "customer_ids": [c["id"] for c in people], "from_period": "next"}
            ], "names": [c["name"] for c in people]}}
        if amounts and (_has(t, EXPENSE) or not people):
            when = _expense_date(t, today)
            return {"intent": "what_if", "args": {"changes": [
                {"type": "new_bill", "name": _expense_name(t), "amount": max(amounts), "date": when.isoformat(),
                 "recurrence": "once"}
            ], "names": []}}

    if _has(t, ADD) and amounts:
        names = _new_student_names(t)
        due = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)\b", t)
        fee = next((a for a in amounts if a >= 300), amounts[0])
        if names:
            return {"intent": "add_customers", "args": {
                "customers": [{"name": n, "monthly_fee": fee, "due_day": int(due.group(1)) if due else 5} for n in names]
            }}

    if _has(t, PAID) and amounts and people and not _has(t, ("hasn't", "haven't", "not paid", "nahi")):
        method = "cash" if _has(t, ("cash", "nakad", "naqad", "haath")) else "upi"
        return {"intent": "record_payment", "args": {
            "customer_id": people[0]["id"], "customer_name": people[0]["name"], "amount": amounts[0], "method": method,
        }}

    if _has(t, CHASE):
        return {"intent": "chase", "args": {}}
    if _has(t, FORECAST):
        days = 90 if "90" in t or "3 month" in t else 30 if "30" in t else 60
        return {"intent": "forecast", "args": {"days": days}}
    if _has(t, DUES) or people:
        return {"intent": "dues", "args": {"customer_ids": [c["id"] for c in people]}}
    return {"intent": "help", "args": {}}
