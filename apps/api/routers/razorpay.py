"""Razorpay payment links (Slice 5).

POST /payment-links/customer/{customer_id}  -> link for that student's oldest unpaid invoice (reused if it exists)
POST /payment-links/sync                    -> check open links with Razorpay; mark paid ones (works without a webhook)
POST /webhooks/razorpay                     -> Razorpay calls this when a link is paid (signature verified)
GET  /payment-links/status                  -> {configured: bool}
"""

import json
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request

from adapters import payments as rzp
from app.deps import get_current_business_id, get_supabase_client, resolve_demo_business_id

router = APIRouter(tags=["payments"])

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _month(period: str | None) -> str:
    if not period:
        return "fees"
    y, m = period.split("-")
    return f"{MONTHS[int(m) - 1]} {y}"


def record_link_payment(client, business_id: str, invoice: dict, payment_id: str, amount_paise: int,
                        method: str = "upi") -> bool:
    """Mark the invoice paid and add a payment row. Idempotent on the Razorpay payment id."""
    existing = (
        client.table("payments").select("id").eq("business_id", business_id).eq("upi_ref", payment_id)
        .limit(1).execute()
    ).data
    if existing:
        return False
    amount = Decimal(amount_paise) / 100
    client.table("payments").insert({
        "business_id": business_id, "invoice_id": invoice["id"], "amount": str(amount),
        "method": method if method in ("upi", "cash", "card", "other") else "other",
        "source": "link_webhook", "payer_text": "Razorpay payment link", "upi_ref": payment_id,
        "received_at": _now(), "match_confidence": 100, "match_status": "matched",
    }).execute()
    status = "paid" if amount >= Decimal(str(invoice["amount"])) else "partially_paid"
    client.table("invoices").update({"status": status, "paid_at": _now()}).eq("id", invoice["id"]).execute()
    return True


@router.get("/payment-links/status")
def link_status() -> dict:
    return {"configured": rzp.is_configured()}


@router.post("/payment-links/customer/{customer_id}")
def link_for_customer(customer_id: str, business_id: str = Depends(get_current_business_id),
                      client=Depends(get_supabase_client)) -> dict:
    if not rzp.is_configured():
        raise HTTPException(503, "Razorpay is not configured")
    customer = (
        client.table("customers").select("id, name, phone").eq("id", customer_id)
        .eq("business_id", business_id).limit(1).execute()
    ).data
    if not customer:
        raise HTTPException(404, "Student not found")
    customer = customer[0]
    invoices = (
        client.table("invoices").select("id, period, amount, due_date, status, payment_link_id, payment_link_url")
        .eq("business_id", business_id).eq("customer_id", customer_id).execute()
    ).data or []
    unpaid = sorted([i for i in invoices if i.get("status") != "paid"], key=lambda i: str(i["due_date"]))
    if not unpaid:
        raise HTTPException(404, "No pending fees for this student")
    invoice = unpaid[0]
    if invoice.get("payment_link_url"):
        return {"url": invoice["payment_link_url"], "invoice_id": invoice["id"], "amount": invoice["amount"],
                "period": invoice.get("period"), "reused": True}
    try:
        link = rzp.create_payment_link(
            invoice_id=invoice["id"], amount=invoice["amount"],
            description=f"{customer['name']} - {_month(invoice.get('period'))} tuition fees",
            customer_name=customer["name"], phone=customer.get("phone"),
        )
    except rzp.RazorpayError as e:
        raise HTTPException(502, str(e))
    client.table("invoices").update({"payment_link_id": link["id"], "payment_link_url": link["short_url"]}).eq(
        "id", invoice["id"]
    ).execute()
    return {"url": link["short_url"], "invoice_id": invoice["id"], "amount": invoice["amount"],
            "period": invoice.get("period"), "reused": False}


@router.post("/payment-links/sync")
def sync_links(business_id: str = Depends(get_current_business_id), client=Depends(get_supabase_client)) -> dict:
    """Ask Razorpay about every open link; record the paid ones. Lets local demos work without a webhook."""
    if not rzp.is_configured():
        return {"checked": 0, "paid": []}
    open_links = [
        i for i in (
            client.table("invoices").select("id, customer_id, amount, status, payment_link_id")
            .eq("business_id", business_id).execute()
        ).data or []
        if i.get("payment_link_id") and i.get("status") != "paid"
    ]
    paid = []
    for inv in open_links[:20]:
        try:
            link = rzp.fetch_payment_link(inv["payment_link_id"])
        except rzp.RazorpayError:
            continue
        if link.get("status") != "paid":
            continue
        payments = link.get("payments") or []
        pay_id = (payments[0].get("payment_id") if payments else None) or f"plink:{inv['payment_link_id']}"
        method = (payments[0].get("method") if payments else None) or "upi"
        if record_link_payment(client, business_id, inv, pay_id, int(link.get("amount_paid") or link["amount"]), method):
            paid.append(inv["id"])
    return {"checked": len(open_links[:20]), "paid": paid}


@router.post("/webhooks/razorpay")
async def razorpay_webhook(request: Request, client=Depends(get_supabase_client)) -> dict:
    body = await request.body()
    if not rzp.verify_webhook(body, request.headers.get("X-Razorpay-Signature")):
        raise HTTPException(400, "Invalid signature")
    event = json.loads(body or b"{}")
    if event.get("event") != "payment_link.paid":
        return {"ok": True, "ignored": event.get("event")}
    link = event["payload"]["payment_link"]["entity"]
    payment = event["payload"].get("payment", {}).get("entity", {})
    invoice_id = link.get("reference_id") or (link.get("notes") or {}).get("invoice_id")
    business_id = resolve_demo_business_id()
    invoice = (
        client.table("invoices").select("id, amount, status").eq("id", invoice_id)
        .eq("business_id", business_id).limit(1).execute()
    ).data
    if not invoice:
        return {"ok": True, "ignored": "unknown invoice"}
    recorded = record_link_payment(client, business_id, invoice[0], payment.get("id") or f"plink:{link['id']}",
                                   int(payment.get("amount") or link.get("amount_paid") or link["amount"]),
                                   payment.get("method") or "upi")
    return {"ok": True, "recorded": recorded}
