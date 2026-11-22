"""Tests for engines/intents.py - the voice command parser."""

from datetime import date

import pytest

from engines.intents import parse_command

TODAY = date(2026, 11, 22)
CUSTOMERS = [
    {"id": "r", "name": "Rohan Sharma", "status": "active"},
    {"id": "a", "name": "Aisha Khan", "status": "active"},
    {"id": "k", "name": "Kabir Mehta", "status": "active"},
    {"id": "p", "name": "Parth Kale", "status": "active"},
    {"id": "l", "name": "Lavanya Rajan", "status": "left"},
]


def p(text):
    return parse_command(text, CUSTOMERS, TODAY)


@pytest.mark.parametrize("text", ["Who hasn't paid this month?", "kitna pending hai", "Who owes me money", "Kaun baaki hai"])
def test_dues(text):
    assert p(text)["intent"] == "dues"


@pytest.mark.parametrize("text", ["Will I manage rent next month?", "Am I going to be short?", "Show my forecast",
                                  "kiraya ka paisa hoga?"])
def test_forecast(text):
    assert p(text)["intent"] == "forecast"


@pytest.mark.parametrize("text", ["Who should I chase today?", "Remind everyone who's late", "kisko call karun"])
def test_chase(text):
    assert p(text)["intent"] == "chase"


def test_what_if_delay():
    r = p("What if Kabir pays 15 days late?")
    assert r["intent"] == "what_if"
    assert r["args"]["changes"] == [{"type": "delay", "customer_id": "k", "days": 15}]


def test_what_if_delay_hinglish_and_misheard_name():
    r = p("agar Kabeer das din late pay kare")
    assert r["intent"] == "what_if"
    assert r["args"]["changes"][0] == {"type": "delay", "customer_id": "k", "days": 10}


def test_what_if_leave():
    r = p("What if Rohan and Aisha leave?")
    assert r["intent"] == "what_if"
    assert r["args"]["changes"][0]["customer_ids"] == ["r", "a"]


def test_what_if_expense_with_date():
    r = p("What if I buy a new projector for 20,000 on 28 Nov?")
    assert r["intent"] == "what_if"
    change = r["args"]["changes"][0]
    assert change["type"] == "new_bill" and change["amount"] == 20000 and change["date"] == "2026-11-28"
    assert "Projector" in change["name"]


@pytest.mark.parametrize("text,method,amount", [
    ("Aisha paid 2500 cash", "cash", 2500),
    ("Rohan ne 3000 diye", "upi", 3000),
    ("Kabir paid two thousand five hundred", "upi", 2500),
    ("Parth gave 3k in cash", "cash", 3000),
])
def test_record_payment(text, method, amount):
    r = p(text)
    assert r["intent"] == "record_payment"
    assert r["args"]["method"] == method
    assert r["args"]["amount"] == amount


def test_not_paid_is_not_a_payment():
    assert p("Has Rohan not paid 3000?")["intent"] != "record_payment"


def test_add_students():
    r = p("New students Ravi and Neha, 2500 each, due on the 5th")
    assert r["intent"] == "add_customers"
    names = [c["name"] for c in r["args"]["customers"]]
    assert names == ["Ravi", "Neha"]
    assert all(c["monthly_fee"] == 2500 and c["due_day"] == 5 for c in r["args"]["customers"])


def test_left_students_are_not_matched():
    assert p("What if Lavanya pays 10 days late?")["intent"] != "what_if" or \
        p("What if Lavanya pays 10 days late?")["args"]["changes"] == []


def test_gibberish_is_help():
    assert p("banana")["intent"] == "help"
    assert p("")["intent"] == "help"
