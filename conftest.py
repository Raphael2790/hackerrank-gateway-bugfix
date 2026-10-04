from datetime import datetime

import pytest

from app import create_app
from app.clock import Clock

START = datetime(2026, 3, 2, 10, 0)  # segunda-feira, 10:00
APPROVED_CARD = "4111111111111111"
OTHER_APPROVED_CARD = "5555444433331111"
DECLINED_CARD = "4000000000000002"


@pytest.fixture
def clock():
    """Relógio da API, parado em START. Ande com clock.advance(days=1, hours=2) ou clock.set(datetime(...))."""
    return Clock(START)


@pytest.fixture
def app(clock):
    return create_app(clock)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def pay(client):
    """Cria um pagamento pela API e devolve a resposta.

    Padrão: lojista 1, R$ 100,00 no crédito à vista, cartão aprovado e captura imediata.
    Troque o que quiser: pay(method="debit"), pay(amount="250.00", installments=3), pay(capture=False).
    pay(key="pedido-1") envia o header Idempotency-Key. Um campo com valor None sai do corpo.
    """

    def _pay(key=None, **fields):
        payload = {
            "merchant_id": 1,
            "amount": "100.00",
            "method": "credit",
            "installments": 1,
            "card_number": APPROVED_CARD,
        }
        payload.update(fields)
        payload = {name: value for name, value in payload.items() if value is not None}
        headers = {"Idempotency-Key": key} if key else {}
        return client.post("/payments", json=payload, headers=headers)

    return _pay
