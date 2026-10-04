from datetime import datetime

import pytest


def receivables(client):
    """Helper para pegar a agenda de recebíveis."""
    resp = client.get("/merchants/1/receivables")
    return resp.get_json()


def test_debit_on_friday_settles_on_monday(client, pay, clock):
    """Débito capturado na sexta deve ser repasse na segunda."""
    clock.set(datetime(2026, 3, 6, 15, 0))  # sexta
    pay(method="debit")

    settle_dates = [r["settle_date"] for r in receivables(client)]
    assert settle_dates == ["2026-03-09"], f"Sexta → esperado segunda (09), obtido {settle_dates}"


def test_debit_on_saturday_settles_on_monday(client, pay, clock):
    """Débito capturado no sábado deve ser repasse na segunda."""
    clock.set(datetime(2026, 3, 7, 15, 0))  # sábado
    pay(method="debit")

    settle_dates = [r["settle_date"] for r in receivables(client)]
    assert settle_dates == ["2026-03-09"], f"Sábado → esperado segunda (09), obtido {settle_dates}"


def test_debit_on_sunday_settles_on_monday(client, pay, clock):
    """Débito capturado no domingo deve ser repasse na segunda."""
    clock.set(datetime(2026, 3, 8, 15, 0))  # domingo
    pay(method="debit")

    settle_dates = [r["settle_date"] for r in receivables(client)]
    assert settle_dates == ["2026-03-09"], f"Domingo → esperado segunda (09), obtido {settle_dates}"


def test_debit_on_monday_settles_on_tuesday(client, pay, clock):
    """Débito capturado na segunda deve ser repasse na terça."""
    clock.set(datetime(2026, 3, 2, 15, 0))  # segunda
    pay(method="debit")

    settle_dates = [r["settle_date"] for r in receivables(client)]
    assert settle_dates == ["2026-03-03"], f"Segunda → esperado terça (03), obtido {settle_dates}"
