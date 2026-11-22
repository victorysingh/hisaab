"""Voice / text agent: a sentence in, a spoken-ready answer out.

POST /agent/turn     {transcript} -> {reply_text, intent, ui_hint, proposed_actions, what_if_changes}
POST /agent/confirm  {action}     -> executes a proposed action (record a payment, add students)

Read-only questions are answered straight away from the engines. Anything that changes data
comes back as a proposed action and only runs after the user confirms. All numbers come from
the engines; the reply text only formats them.
"""

from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.deps import get_current_business_id, get_supabase_client
from engines.forecast import build_forecast, fmt_rs, what_if
from engines.intents import parse_command
from routers.dashboard import get_dues
from routers.forecast import _load_inputs, _today

router = APIRouter(prefix="/agent", tags=["agent"])

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
HELP = ("Try: \"Who hasn't paid?\", \"Will I manage rent next month?\", "
        "\"What if Kabir pays 15 days late?\", \"Aisha paid 2500 cash\" or \"Who should I chase today?\"")


class TurnRequest(BaseModel):
    transcript: str
    language: str | None = None


class ConfirmRequest(BaseModel):
    action: dict


def rs(value) -> str:
    return fmt_rs(Decimal(str(value))).replace("Rs ", "₹")


def day(iso) -> str:
    d = date.fromisoformat(str(iso)[:10])
    return f"{d.day} {MONTHS[d.month - 1]}"


def first(name: str) -> str:
    return name.split()[0]


def join_names(names: list[str]) -> str:
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"


def ordinal(n: int) -> str:
    return f"{n}{'th' if 11 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def lowest(f: dict) -> tuple[Decimal, str] | None:
    """Deepest shortfall below the safety line in the likely case: (amount short, date) or None."""
    buffer = Decimal(str(f.get("safety_buffer") or 0))
    worst = min(f["days"], key=lambda d: Decimal(str(d["likely"])))
    gap = buffer - Decimal(str(worst["likely"]))
    return (gap, worst["date"]) if gap > 0 else None


def next_period(today: date) -> str:
    y, m = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
    return f"{y}-{m:02d}"


def _customers(client, business_id: str) -> list[dict]:
    return (
        client.table("customers").select("id, name, status, monthly_fee, due_day")
        .eq("business_id", business_id).execute()
    ).data or []


def _log(client, business_id: str, transcript: str, intent: str, tool: str | None, args: dict | None,
         result: dict | None, confirmed: bool) -> None:
    try:
        client.table("agent_events").insert({
            "business_id": business_id, "transcript": transcript, "language": "en-IN", "intent": intent,
            "tool_name": tool, "tool_args": args, "result": result, "confirmed": confirmed,
        }).execute()
    except Exception:  # logging must never break the conversation
        pass


def _shortfall_sentence(f: dict) -> str:
    s = f.get("shortfall")
    if s:
        return f"You'll be {rs(s['amount'])} short on {day(s['date'])}."
    return f"You're covered for the next {f['days_ahead']} days."


def _chase(rows: list, target: Decimal) -> list:
    ordered = sorted(rows, key=lambda r: (r.invoice_count >= 3, -r.total_due, -r.days_late))
    picked, total = [], Decimal("0")
    for r in ordered:
        if len(picked) >= 3 or (target > 0 and total >= target):
            break
        picked.append(r)
        total += r.total_due
    return picked


@router.post("/turn")
def turn(body: TurnRequest, business_id: str = Depends(get_current_business_id),
         client=Depends(get_supabase_client)) -> dict:
    today = _today()
    customers = _customers(client, business_id)
    parsed = parse_command(body.transcript, customers, today)
    intent, args = parsed["intent"], parsed["args"]
    out = {"intent": intent, "reply_text": HELP, "ui_hint": None, "proposed_actions": [], "what_if_changes": None}

    if intent == "dues":
        dues = get_dues(business_id=business_id, client=client)
        rows = dues.rows
        wanted = set(args.get("customer_ids") or [])
        if wanted:
            names = {c["id"]: c["name"] for c in customers}
            lines = []
            for cid in wanted:
                row = next((r for r in rows if r.customer_id == cid), None)
                lines.append(f"{first(names[cid])} owes {rs(row.total_due)} since {day(row.oldest_due_date)}."
                             if row else f"{first(names[cid])} has no pending fees.")
            out["reply_text"] = " ".join(lines)
        elif rows:
            top = max(rows, key=lambda r: r.days_late)
            out["reply_text"] = (f"{len(rows)} student{'s' if len(rows) != 1 else ''} owe{'' if len(rows) != 1 else 's'} you {rs(dues.totals.total_outstanding)}. "
                                 f"Longest pending: {top.customer_name}, {rs(top.total_due)} since {day(top.oldest_due_date)}.")
        else:
            out["reply_text"] = "Everyone has paid. Nobody owes you anything right now."
        out["ui_hint"] = "show_dues"

    elif intent == "forecast":
        f = build_forecast(today=today, days=args.get("days", 60), **_load_inputs(client, business_id, today))
        reply = _shortfall_sentence(f)
        if f.get("causes"):
            reply += f" Biggest reasons: {', '.join(c['label'] for c in f['causes'][:2])}."
        out["reply_text"] = reply
        out["ui_hint"] = "show_forecast"

    elif intent == "chase":
        dues = get_dues(business_id=business_id, client=client)
        f = build_forecast(today=today, days=60, **_load_inputs(client, business_id, today))
        target = Decimal(str(f["shortfall"]["amount"])) if f.get("shortfall") else Decimal("0")
        picked = _chase(dues.rows, target)
        if not picked:
            out["reply_text"] = "Nobody to chase. Everyone has paid."
        else:
            total = sum((r.total_due for r in picked), Decimal("0"))
            reply = f"Chase {join_names([first(r.customer_name) for r in picked])} today: {rs(total)} pending."
            if target > 0:
                reply += (" That covers" if total >= target else " That helps with") + \
                         f" the {rs(target)} shortfall on {day(f['shortfall']['date'])}."
            out["reply_text"] = reply
        out["ui_hint"] = "show_home"

    elif intent == "what_if":
        changes = args["changes"]
        for ch in changes:
            if ch.get("from_period") == "next":
                ch["from_period"] = next_period(today)
        inputs = _load_inputs(client, business_id, today)
        result = what_if(baseline_kwargs={"today": today, "days": 60, **inputs}, changes=changes)
        names = args.get("names") or []
        ch = changes[0]
        if ch["type"] == "delay":
            lead = f"If {join_names([first(n) for n in names])} pay{'s' if len(names) == 1 else ''} {ch['days']} days late"
        elif ch["type"] == "drop":
            lead = f"If {join_names([first(n) for n in names])} leave{'s' if len(names) == 1 else ''}"
        else:
            lead = f"If you spend {rs(ch['amount'])} on {ch['name'].lower()} on {day(ch['date'])}"
        now, before = lowest(result), lowest(result["baseline"])
        if now:
            tail = f"you'll be up to {rs(now[0])} short, lowest on {day(now[1])}"
            if before and now[0] != before[0]:
                tail += f", instead of {rs(before[0])}"
            elif before:
                tail += ", no change from now"
            elif not before:
                tail += ". Right now you're covered"
        else:
            tail = "you're still covered for the next 60 days"
        out["reply_text"] = f"{lead}, {tail}."
        out["ui_hint"] = "show_forecast"
        out["what_if_changes"] = changes

    elif intent == "record_payment":
        summary = f"Mark {args['customer_name']} {rs(args['amount'])} paid ({'cash' if args['method'] == 'cash' else 'UPI'})"
        out["proposed_actions"] = [{"tool": "record_payment", "args": args, "summary": summary}]
        out["reply_text"] = f"{summary}?"

    elif intent == "add_customers":
        new = args["customers"]
        summary = (f"Add {join_names([c['name'] for c in new])} at {rs(new[0]['monthly_fee'])} a month, "
                   f"due on the {ordinal(int(new[0]['due_day']))}")
        out["proposed_actions"] = [{"tool": "add_customers", "args": args, "summary": summary}]
        out["reply_text"] = f"{summary}?"

    _log(client, business_id, body.transcript, intent, None, args, {"reply": out["reply_text"]}, False)
    return out


@router.post("/confirm")
def confirm(body: ConfirmRequest, business_id: str = Depends(get_current_business_id),
            client=Depends(get_supabase_client)) -> dict:
    tool = body.action.get("tool")
    args = body.action.get("args") or {}
    now = datetime.now(timezone.utc).isoformat()

    if tool == "record_payment":
        customer = (
            client.table("customers").select("id, name").eq("id", args.get("customer_id"))
            .eq("business_id", business_id).limit(1).execute()
        ).data
        if not customer:
            raise HTTPException(404, "Student not found")
        amount = Decimal(str(args.get("amount") or 0))
        if amount <= 0:
            raise HTTPException(422, "Amount must be positive")
        unpaid = sorted(
            [i for i in (client.table("invoices").select("id, amount, due_date, status")
                         .eq("business_id", business_id).eq("customer_id", customer[0]["id"]).execute()).data or []
             if i.get("status") != "paid"],
            key=lambda i: str(i["due_date"]),
        )
        invoice = unpaid[0] if unpaid else None
        client.table("payments").insert({
            "business_id": business_id, "invoice_id": invoice["id"] if invoice else None, "amount": str(amount),
            "method": "cash" if args.get("method") == "cash" else "upi", "source": "voice",
            "payer_text": customer[0]["name"], "received_at": now, "match_confidence": 100,
            "match_status": "matched" if invoice else "unmatched",
        }).execute()
        if invoice:
            status = "paid" if amount >= Decimal(str(invoice["amount"])) else "partially_paid"
            client.table("invoices").update({"status": status, "paid_at": now}).eq("id", invoice["id"]).execute()
            reply = f"Done. {rs(amount)} from {customer[0]['name']} recorded for {day(invoice['due_date'])}."
        else:
            reply = f"Done. {rs(amount)} from {customer[0]['name']} recorded as an advance."
        _log(client, business_id, "", "record_payment", tool, args, {"reply": reply}, True)
        return {"reply_text": reply, "ui_hint": "refresh"}

    if tool == "add_customers":
        added = []
        for c in args.get("customers") or []:
            name = str(c.get("name") or "").strip()
            fee = Decimal(str(c.get("monthly_fee") or 0))
            if not name or fee <= 0:
                continue
            client.table("customers").insert({
                "business_id": business_id, "name": name, "monthly_fee": str(fee),
                "due_day": int(c.get("due_day") or 5), "status": "active",
            }).execute()
            added.append(name)
        if not added:
            raise HTTPException(422, "Nothing to add")
        reply = f"Added {join_names(added)}."
        _log(client, business_id, "", "add_customers", tool, args, {"reply": reply}, True)
        return {"reply_text": reply, "ui_hint": "refresh"}

    raise HTTPException(422, f"Unknown action: {tool}")
