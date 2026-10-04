import pytest

from conftest import DECLINED_CARD


def test_get_merchant(client):
    resp = client.get("/merchants/1")

    assert resp.status_code == 200
    assert resp.get_json() == {"id": 1, "name": "Loja Aurora"}


def test_unknown_merchant_returns_404(client, pay):
    assert client.get("/merchants/99").status_code == 404
    assert pay(merchant_id=99).status_code == 404


def test_credit_payment_is_captured_by_default(pay):
    resp = pay()

    assert resp.status_code == 201
    payment = resp.get_json()
    assert payment["status"] == "CAPTURED"
    assert payment["amount"] == "100.00"
    assert payment["captured_amount"] == "100.00"
    assert payment["fee"] == "2.99"
    assert payment["net_amount"] == "97.01"
    assert payment["card_last4"] == "1111"
    assert payment["created_at"] == "2026-03-02T10:00:00"


def test_installment_credit_uses_installment_rate(pay):
    payment = pay(amount="250.00", installments=3).get_json()

    assert payment["fee"] == "9.98"  # 3,99% de 250,00 = 9,975
    assert payment["net_amount"] == "240.02"


def test_pix_and_debit_are_always_captured(pay):
    pix = pay(method="pix", capture=False).get_json()
    debit = pay(method="debit", capture=False).get_json()

    assert (pix["status"], pix["fee"], pix["card_last4"]) == ("CAPTURED", "0.99", None)
    assert (debit["status"], debit["fee"]) == ("CAPTURED", "1.99")


def test_pre_authorization_is_not_captured(pay):
    payment = pay(capture=False).get_json()

    assert payment["status"] == "AUTHORIZED"
    assert payment["captured_amount"] == "0.00"
    assert payment["fee"] == "0.00"
    assert payment["captured_at"] is None


def test_amount_can_be_sent_as_number(pay):
    assert pay(amount=59.9).get_json()["amount"] == "59.90"


@pytest.mark.parametrize("amount", ["0", "-10.00", "10.001", "abc", True])
def test_invalid_amount_returns_400(pay, amount):
    assert pay(amount=amount).status_code == 400


@pytest.mark.parametrize(
    "fields",
    [
        {"card_number": "1234"},
        {"installments": 13},
        {"installments": 0},
        {"method": "pix", "installments": 2},
        {"method": "debit", "installments": 3},
        {"method": "boleto"},
    ],
)
def test_invalid_payment_returns_400(pay, fields):
    assert pay(**fields).status_code == 400


def test_declined_payments_return_402_and_create_nothing(client, pay):
    assert pay(card_number=DECLINED_CARD).status_code == 402
    assert pay(amount="5000.01").status_code == 402  # acima do limite

    assert client.get("/payments/1").status_code == 404
