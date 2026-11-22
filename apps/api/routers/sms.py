"""SMS payment routes: parse a bank/UPI SMS, match it to an invoice, record the payment.

POST /sms/parse                        {text} -> parsed event (debug / simulator preview)
POST /payments/ingest                  {text} or {amount, payer_text, upi_id, upi_ref} -> match result
POST /payments/{payment_id}/confirm-match  {invoice_id | null} -> confirm or reject a suggested match
GET  /payments/review                  payments waiting for a human decision
"""

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.deps import get_current_business_id, get_supabase_client
from engines.forecast import delay_stats
from engines.matching import match_payment
from engines.sms_parser import parse_sms
from routers.forecast import _today

router = APIRouter(tags=["sms"])


class ParseRequest(BaseModel):
    text: str


class IngestRequest(BaseModel):
    text: str | None = None
    amount: Decimal | None = None
    payer_text: str | None = None
    upi_id: str | None = None
    upi_ref: str | None = None
    received_at: str | None = None


class ConfirmRequest(BaseModel):
    invoice_id: str | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _jsonable(event: dict | None) -> dict | None:
    if event is None:
        return None
    return {k: (str(v) if isinstance(v, Decimal) else v) for k, v in event.items()}


def _load(client, business_id: str) -> tuple[list[dict], list[dict], list[dict]]:
    customers = (
        client.table("customers").select("id, name, guardian_name, monthly_fee, status")
        .eq("business_id", business_id).execute()
    ).data or []
    invoices = (
        client.table("invoices").select("id, customer_id, period, amount, due_date, status, paid_at")
        .eq("business_id", business_id).limit(5000).execute()
    ).data or []
    ids = [c["id"] for c in customers]
    aliases = (
        client.table("payer_aliases").select("customer_id, alias_type, alias_value")
        .in_("customer_id", ids).execute()
    ).data if ids else []
    return customers, invoices, aliases or []


def _mark_invoice_paid(client, business_id: str, invoice: dict, amount: Decimal, paid_at: str) -> None:
    new_status = "paid" if amount >= Decimal(str(invoice["amount"])) else "partially_paid"
    client.table("invoices").update({"status": new_status, "paid_at": paid_at}).eq("id", invoice["id"]).eq(
        "business_id", business_id
    ).execute()


def _save_aliases(client, customer_id: str, upi_id: str | None, payer_text: str | None) -> None:
    existing = (
        client.table("payer_aliases").select("alias_type, alias_value").eq("customer_id", customer_id).execute()
    ).data or []
    have = {(a["alias_type"], (a["alias_value"] or "").lower()) for a in existing}
    for alias_type, value in (("upi_id", upi_id), ("payer_name", payer_text)):
        if value and (alias_type, value.lower()) not in have:
            client.table("payer_aliases").insert({
                "customer_id": customer_id,
                "alias_type": alias_type,
                "alias_value": value.lower() if alias_type == "upi_id" else value,
                "confirmed_at": _now_iso(),
            }).execute()


@router.post("/sms/parse")
def parse(body: ParseRequest) -> dict:
    event = parse_sms(body.text)
    if event is None:
        return {"is_payment": False, "parsed": None}
    return {"is_payment": True, "parsed": _jsonable(event)}


@router.post("/payments/ingest")
def ingest(
    body: IngestRequest,
    business_id: str = Depends(get_current_business_id),
    client=Depends(get_supabase_client),
) -> dict:
    if body.text:
        event = parse_sms(body.text)
        if event is None:
            return {"status": "ignored", "reason": "Not a payment credit SMS", "parsed": None}
    elif body.amount:
        event = {"amount": body.amount, "payer_text": body.payer_text, "upi_id": body.upi_id,
                 "upi_ref": body.upi_ref, "is_credit": True}
    else:
        raise HTTPException(422, "Send either text or amount")

    if event.get("upi_ref"):
        dup = (
            client.table("payments").select("id, match_status, invoice_id")
            .eq("business_id", business_id).eq("upi_ref", event["upi_ref"]).limit(1).execute()
        ).data
        if dup:
            return {"status": "duplicate", "payment_id": dup[0]["id"], "parsed": _jsonable(event),
                    "reason": "This UPI reference was already recorded"}

    customers, invoices, aliases = _load(client, business_id)
    result = match_payment(event, invoices, customers, aliases, _today(), delay_stats(invoices))
    received_at = body.received_at or _now_iso()

    inserted = client.table("payments").insert({
        "business_id": business_id,
        "invoice_id": result["invoice_id"],
        "amount": str(event["amount"]),
        "method": "upi",
        "source": "sms",
        "payer_text": event.get("payer_text"),
        "upi_id": event.get("upi_id"),
        "upi_ref": event.get("upi_ref"),
        "received_at": received_at,
        "match_confidence": result["confidence"],
        "match_status": result["status"],
    }).execute().data
    payment_id = inserted[0]["id"] if inserted else None

    customer_name = None
    if result["status"] == "matched":
        invoice = next(i for i in invoices if i["id"] == result["invoice_id"])
        _mark_invoice_paid(client, business_id, invoice, Decimal(str(event["amount"])), received_at)
        _save_aliases(client, result["customer_id"], event.get("upi_id"), event.get("payer_text"))
        customer_name = next((c["name"] for c in customers if c["id"] == result["customer_id"]), None)

    return {
        "status": result["status"],
        "payment_id": payment_id,
        "confidence": result["confidence"],
        "invoice_id": result["invoice_id"],
        "customer_name": customer_name,
        "candidates": [{**c, "amount": str(c["amount"])} for c in result["candidates"]],
        "parsed": _jsonable(event),
    }


@router.post("/payments/{payment_id}/confirm-match")
def confirm_match(
    payment_id: str,
    body: ConfirmRequest,
    business_id: str = Depends(get_current_business_id),
    client=Depends(get_supabase_client),
) -> dict:
    payment = (
        client.table("payments").select("id, amount, payer_text, upi_id, received_at, match_status")
        .eq("id", payment_id).eq("business_id", business_id).limit(1).execute()
    ).data
    if not payment:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Payment not found")
    payment = payment[0]

    if body.invoice_id is None:
        client.table("payments").update({"match_status": "unmatched"}).eq("id", payment_id).execute()
        return {"status": "unmatched", "payment_id": payment_id}

    invoice = (
        client.table("invoices").select("id, customer_id, amount, status")
        .eq("id", body.invoice_id).eq("business_id", business_id).limit(1).execute()
    ).data
    if not invoice:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invoice not found")
    invoice = invoice[0]

    client.table("payments").update({"invoice_id": invoice["id"], "match_status": "matched"}).eq(
        "id", payment_id
    ).execute()
    _mark_invoice_paid(client, business_id, invoice, Decimal(str(payment["amount"])),
                       payment.get("received_at") or _now_iso())
    _save_aliases(client, invoice["customer_id"], payment.get("upi_id"), payment.get("payer_text"))
    name = (
        client.table("customers").select("name").eq("id", invoice["customer_id"]).limit(1).execute()
    ).data
    return {"status": "matched", "payment_id": payment_id, "invoice_id": invoice["id"],
            "customer_name": name[0]["name"] if name else None}


@router.get("/payments/review")
def review_queue(
    business_id: str = Depends(get_current_business_id),
    client=Depends(get_supabase_client),
) -> list[dict]:
    return (
        client.table("payments").select("id, amount, payer_text, upi_id, upi_ref, received_at, match_confidence")
        .eq("business_id", business_id).eq("match_status", "needs_review").execute()
    ).data or []
