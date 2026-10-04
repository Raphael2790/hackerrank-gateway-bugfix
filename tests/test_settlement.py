from datetime import datetime
from decimal import Decimal

from app.services.settlement import split_evenly


def receivables(client, merchant_id=1):
    return client.get(f"/merchants/{merchant_id}/receivables").get_json()


def test_pix_settles_on_capture_day(client, pay):
    pay(method="pix")

    assert receivables(client) == [
        {"payment_id": 1, "installment": 1, "amount": "99.01", "settle_date": "2026-03-02", "kind": "SALE"}
    ]


def test_debit_settles_next_day(client, pay):
    pay(method="debit")

    assert [(r["amount"], r["settle_date"]) for r in receivables(client)] == [("98.01", "2026-03-03")]


def test_debit_on_saturday_settles_on_monday(client, pay, clock):
    clock.set(datetime(2026, 3, 7, 11, 0))  # sábado

    pay(method="debit")

    assert [r["settle_date"] for r in receivables(client)] == ["2026-03-09"]


def test_debit_on_friday_settles_on_monday(client, pay, clock):
    clock.set(datetime(2026, 3, 6, 15, 0))  # sexta

    pay(method="debit")

    assert [r["settle_date"] for r in receivables(client)] == ["2026-03-09"]


def test_credit_installments_schedule(client, pay):
    pay(amount="250.00", installments=3)  # líquido: 240,02

    assert [(r["installment"], r["amount"], r["settle_date"]) for r in receivables(client)] == [
        (1, "80.02", "2026-04-01"),
        (2, "80.00", "2026-05-01"),
        (3, "80.00", "2026-06-01"),  # 31/05 é domingo
    ]


def test_split_evenly_sends_remainder_to_first_part():
    assert split_evenly(Decimal("100.00"), 3) == [Decimal("33.34"), Decimal("33.33"), Decimal("33.33")]


def test_receivables_are_per_merchant(client, pay):
    pay(merchant_id=1)
    pay(merchant_id=2, method="pix")

    assert len(receivables(client, 1)) == 1
    assert [r["amount"] for r in receivables(client, 2)] == ["99.01"]


def test_authorization_does_not_create_receivables(client, pay):
    pay(capture=False)

    assert receivables(client) == []


def test_balance_available_and_pending(client, pay):
    pay(method="pix")  # 99,01 hoje
    pay(method="debit")  # 98,01 amanhã

    today = client.get("/merchants/1/balance").get_json()
    tomorrow = client.get("/merchants/1/balance?date=2026-03-03").get_json()

    assert today == {"merchant_id": 1, "date": "2026-03-02", "available": "99.01", "pending": "98.01"}
    assert (tomorrow["available"], tomorrow["pending"]) == ("197.02", "0.00")


def test_balance_with_invalid_date_returns_400(client):
    assert client.get("/merchants/1/balance?date=03/03/2026").status_code == 400
