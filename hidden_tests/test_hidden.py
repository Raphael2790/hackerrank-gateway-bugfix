"""Testes ocultos — simulam a correção automática da plataforma.

NÃO abra este arquivo (nem deixe sua IA abrir) antes de terminar o desafio.
"""
from datetime import date, datetime

import pytest

from app.services.settlement import next_business_day
from conftest import DECLINED_CARD, OTHER_APPROVED_CARD


def receivables(client, merchant_id=1):
    return client.get(f"/merchants/{merchant_id}/receivables").get_json()


def status(client, payment_id):
    return client.get(f"/payments/{payment_id}").get_json()["status"]


def run_expire_job(client):
    return client.post("/jobs/expire-authorizations").get_json()["expired"]


def authorize(pay, **fields):
    return pay(capture=False, **fields).get_json()["id"]


# ---------- dias úteis ----------

@pytest.mark.parametrize(
    "day, expected",
    [
        (date(2026, 3, 2), date(2026, 3, 2)),  # segunda
        (date(2026, 3, 3), date(2026, 3, 3)),
        (date(2026, 3, 4), date(2026, 3, 4)),
        (date(2026, 3, 5), date(2026, 3, 5)),
        (date(2026, 3, 6), date(2026, 3, 6)),  # sexta
        (date(2026, 3, 7), date(2026, 3, 9)),  # sábado
        (date(2026, 3, 8), date(2026, 3, 9)),  # domingo
    ],
)
def test_next_business_day(day, expected):
    assert next_business_day(day) == expected


def test_credit_installment_on_saturday_moves_to_monday(client, pay, clock):
    clock.set(datetime(2026, 3, 5, 9, 30))  # quinta: +30 dias cai no sábado, 04/04

    pay(amount="300.00", installments=2)

    assert [r["settle_date"] for r in receivables(client)] == ["2026-04-06", "2026-05-04"]


def test_saturday_balance_does_not_include_friday_debit(client, pay, clock):
    clock.set(datetime(2026, 3, 6, 15, 0))  # sexta
    pay(method="debit")  # líquido: 98,01

    saturday = client.get("/merchants/1/balance?date=2026-03-07").get_json()
    monday = client.get("/merchants/1/balance?date=2026-03-09").get_json()

    assert (saturday["available"], saturday["pending"]) == ("0.00", "98.01")
    assert (monday["available"], monday["pending"]) == ("98.01", "0.00")


def test_pix_on_saturday_settles_the_same_day(client, pay, clock):
    clock.set(datetime(2026, 3, 7, 11, 0))  # sábado

    pay(method="pix")

    assert [r["settle_date"] for r in receivables(client)] == ["2026-03-07"]


# ---------- idempotência ----------

def test_retry_after_card_block_creates_a_single_payment(client, pay, clock):
    for _ in range(3):
        pay(amount="6000.00")
    assert pay(key="pedido-9").status_code == 429
    clock.advance(hours=1, minutes=5)

    first = pay(key="pedido-9")
    replay = pay(key="pedido-9")

    assert (first.status_code, replay.status_code) == (201, 200)
    assert replay.get_json()["id"] == first.get_json()["id"]
    assert client.get(f"/payments/{first.get_json()['id'] + 1}").status_code == 404


def test_retry_after_invalid_card_number_with_fixed_body(pay):
    assert pay(key="pedido-9", card_number="1234").status_code == 400

    assert pay(key="pedido-9").status_code == 201


def test_retry_of_invalid_request_with_same_key_is_still_400(pay):
    assert pay(key="pedido-9", installments=13).status_code == 400

    assert pay(key="pedido-9", installments=13).status_code == 400


def test_retry_after_declined_card_with_other_card(pay):
    assert pay(key="pedido-9", card_number=DECLINED_CARD).status_code == 402

    assert pay(key="pedido-9", card_number=OTHER_APPROVED_CARD).status_code == 201


def test_replay_after_success_does_not_charge_twice(client, pay):
    first = pay(key="pedido-9", installments=2).get_json()

    for _ in range(2):
        replay = pay(key="pedido-9", installments=2)
        assert replay.status_code == 200
        assert replay.get_json()["id"] == first["id"]

    assert len(receivables(client)) == 2
    assert client.get(f"/payments/{first['id'] + 1}").status_code == 404


def test_key_of_successful_payment_rejects_other_body(pay):
    assert pay(key="pedido-9").status_code == 201

    assert pay(key="pedido-9", card_number=OTHER_APPROVED_CARD).status_code == 422


# ---------- expiração de autorizações ----------

def test_expire_job_expires_every_stale_authorization(client, pay, clock):
    ids = [authorize(pay) for _ in range(3)]
    clock.advance(days=8)

    assert sorted(run_expire_job(client)) == ids
    assert [status(client, payment_id) for payment_id in ids] == ["EXPIRED"] * 3


def test_expire_job_with_many_merchants(client, pay, clock):
    old = [authorize(pay, merchant_id=merchant_id) for merchant_id in (1, 2, 1, 2, 1)]
    clock.advance(days=5)
    recent = authorize(pay, merchant_id=2)
    clock.advance(days=2)  # as antigas têm 7 dias; a recente, 2

    assert sorted(run_expire_job(client)) == old
    assert status(client, recent) == "AUTHORIZED"


def test_expired_authorizations_cannot_be_captured_or_voided(client, pay, clock):
    ids = [authorize(pay) for _ in range(4)]
    clock.advance(days=7, hours=1)
    run_expire_job(client)

    for payment_id in ids:
        assert client.post(f"/payments/{payment_id}/capture").status_code == 409
        assert client.post(f"/payments/{payment_id}/void").status_code == 409


def test_second_run_of_expire_job_finds_nothing(client, pay, clock):
    ids = [authorize(pay) for _ in range(2)]
    clock.advance(days=9)

    assert sorted(run_expire_job(client)) == ids
    assert run_expire_job(client) == []


def test_expire_job_ignores_captured_and_voided_payments(client, pay, clock):
    captured, voided, pending = [authorize(pay) for _ in range(3)]
    client.post(f"/payments/{captured}/capture")
    client.post(f"/payments/{voided}/void")
    clock.advance(days=8)

    assert run_expire_job(client) == [pending]
    assert [status(client, payment_id) for payment_id in (captured, voided, pending)] == [
        "CAPTURED",
        "VOIDED",
        "EXPIRED",
    ]


def test_authorization_expires_at_exactly_seven_days(client, pay, clock):
    payment_id = authorize(pay)

    clock.advance(days=6, hours=23, minutes=59)
    assert run_expire_job(client) == []
    clock.advance(minutes=1)
    assert run_expire_job(client) == [payment_id]


# ---------- regras gerais ----------

def test_partial_capture_schedules_only_the_captured_net(client, pay):
    payment_id = authorize(pay, amount="300.00", installments=2)

    payment = client.post(f"/payments/{payment_id}/capture", json={"amount": "200.00"}).get_json()

    assert (payment["fee"], payment["net_amount"]) == ("7.98", "192.02")
    assert [(r["amount"], r["settle_date"]) for r in receivables(client)] == [
        ("96.01", "2026-04-01"),
        ("96.01", "2026-05-01"),
    ]


def test_refund_is_limited_to_the_captured_amount(client, pay):
    payment_id = authorize(pay, amount="300.00")
    client.post(f"/payments/{payment_id}/capture", json={"amount": "100.00"})
    url = f"/payments/{payment_id}/refund"

    assert client.post(url, json={"amount": "100.01"}).status_code == 409
    assert client.post(url).get_json()["payment"]["status"] == "REFUNDED"


def test_attempts_while_blocked_do_not_extend_the_block(pay, clock):
    for _ in range(3):
        pay(amount="6000.00")
    for _ in range(3):
        clock.advance(minutes=10)
        assert pay().status_code == 429
    clock.advance(minutes=30)  # 1 hora depois da 3ª recusa

    assert pay().status_code == 201
