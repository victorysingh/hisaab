"""Tests for engines/sms_parser.py and engines/matching.py (pure, offline)."""

from datetime import date
from decimal import Decimal

import pytest

from engines.matching import match_payment, name_score
from engines.sms_parser import parse_sms

TODAY = date(2026, 11, 22)

CREDITS = [
    (
        "Rs 3,000.00 credited to A/c XX1234 on 22-11-26 by VPA rohan.sharma@okaxis (UPI Ref No 452198763012). -HDFC Bank",
        {"amount": Decimal("3000.00"), "upi_id": "rohan.sharma@okaxis", "upi_ref": "452198763012", "payer": "Rohan Sharma"},
    ),
    (
        "INR 2500 received from AISHA KHAN via UPI on 22-Nov-26. Ref no 334455667788. Avl Bal INR 15,420.50",
        {"amount": Decimal("2500"), "upi_id": None, "upi_ref": "334455667788", "payer": "Aisha Khan"},
    ),
    (
        "Rs.3000 deposited in your A/c XX9876 on 22NOV26. Info: UPI/CR/123456789012/RAVI KUMAR/SBIN/ravik@oksbi",
        {"amount": Decimal("3000"), "upi_id": "ravik@oksbi", "upi_ref": "123456789012", "payer": "Ravi Kumar"},
    ),
    (
        "Dear Customer, Acct XX4321 is credited with ₹2,500.00 on 22-Nov-26 from kabir.mehta.12@ybl. UPI Ref:998877665544 -ICICI",
        {"amount": Decimal("2500.00"), "upi_id": "kabir.mehta.12@ybl", "upi_ref": "998877665544", "payer": "Kabir Mehta"},
    ),
    (
        "Your a/c no. XXXXXXXX5566 is credited by Rs.2,500.00 on 22-11-2026 by a/c linked to VPA nidhi.agarwal@paytm (UPI Ref no 667788990011).",
        {"amount": Decimal("2500.00"), "upi_id": "nidhi.agarwal@paytm", "upi_ref": "667788990011", "payer": "Nidhi Agarwal"},
    ),
]

NOT_CREDITS = [
    "Rs 450.00 debited from A/c XX1234 on 22-11-26 to VPA swiggy@icici (UPI Ref No 123412341234). Not you? Call 18002586161",
    "123456 is your OTP for UPI transaction of Rs 3000. Do not share it with anyone.",
    "Congrats! You have won a cashback of Rs 500 on your next recharge. Offer valid till 30 Nov.",
    "Get a pre-approved loan of Rs 2,00,000 at 10.5%. Apply now.",
    "Your electricity bill of Rs 1,800 is due on 15-Dec. Pay now to avoid late fee.",
]


@pytest.mark.parametrize("text,expected", CREDITS)
def test_parses_credit_messages(text, expected):
    event = parse_sms(text)
    assert event is not None
    assert event["amount"] == expected["amount"]
    assert event["upi_id"] == expected["upi_id"]
    assert event["upi_ref"] == expected["upi_ref"]
    assert event["payer_text"] == expected["payer"]


@pytest.mark.parametrize("text", NOT_CREDITS)
def test_ignores_debits_otps_promos_and_bills(text):
    assert parse_sms(text) is None


# ---------- matching ----------

CUSTOMERS = [
    {"id": "r", "name": "Rohan Sharma", "guardian_name": "Mr. Sharma", "monthly_fee": "3000"},
    {"id": "a", "name": "Aarav Gupta", "guardian_name": "Mr. Gupta", "monthly_fee": "3000"},
    {"id": "k", "name": "Kabir Mehta", "guardian_name": "Mr. Mehta", "monthly_fee": "2500"},
    {"id": "n", "name": "Nidhi Agarwal", "guardian_name": "Mrs. Agarwal", "monthly_fee": "2500"},
]
INVOICES = [
    {"id": "inv-r", "customer_id": "r", "period": "2026-11", "amount": "3000", "due_date": "2026-11-05", "status": "overdue"},
    {"id": "inv-a", "customer_id": "a", "period": "2026-11", "amount": "3000", "due_date": "2026-11-05", "status": "overdue"},
    {"id": "inv-k", "customer_id": "k", "period": "2026-11", "amount": "2500", "due_date": "2026-11-05", "status": "overdue"},
    {"id": "inv-n", "customer_id": "n", "period": "2026-11", "amount": "2500", "due_date": "2026-11-05", "status": "overdue"},
    {"id": "inv-old", "customer_id": "r", "period": "2026-10", "amount": "3000", "due_date": "2026-10-05", "status": "paid"},
]
ALIASES = [{"customer_id": "r", "alias_type": "upi_id", "alias_value": "rohan.sharma@okaxis"}]
STATS = {"r": (0, 2, 5), "a": (0, 3, 20), "k": (10, 18, 22), "n": (5, 15, 20)}


def run(event):
    return match_payment(event, INVOICES, CUSTOMERS, ALIASES, TODAY, STATS)


def test_known_upi_id_and_exact_amount_auto_matches():
    result = run({"amount": Decimal("3000"), "upi_id": "rohan.sharma@okaxis", "payer_text": "Rohan Sharma"})
    assert result["status"] == "matched"
    assert result["invoice_id"] == "inv-r"
    assert result["confidence"] >= 90


def test_full_name_match_without_alias_auto_matches():
    result = run({"amount": Decimal("2500"), "upi_id": "kabir.mehta.12@ybl", "payer_text": "Kabir Mehta"})
    assert result["status"] == "matched"
    assert result["invoice_id"] == "inv-k"


def test_ambiguous_payer_needs_review_with_candidates():
    result = run({"amount": Decimal("2500"), "upi_id": None, "payer_text": "M K"})
    assert result["status"] == "needs_review"
    assert result["invoice_id"] is None
    ids = {c["customer_id"] for c in result["candidates"]}
    assert {"k", "n"} <= ids


def test_unknown_amount_and_payer_is_unmatched():
    result = run({"amount": Decimal("777"), "upi_id": "random@okhdfc", "payer_text": "Zed Q"})
    assert result["status"] == "unmatched"


def test_paid_invoices_are_never_candidates():
    result = run({"amount": Decimal("3000"), "upi_id": "rohan.sharma@okaxis", "payer_text": "Rohan Sharma"})
    assert all(c["invoice_id"] != "inv-old" for c in result["candidates"])


def test_name_score_handles_titles_and_initials():
    assert name_score("Rohan Sharma", "Rohan Sharma") == 30
    assert name_score("R Sharma", "Rohan Sharma", "Mr. Sharma") >= 20
    assert name_score("Zed Q", "Rohan Sharma") < 15
