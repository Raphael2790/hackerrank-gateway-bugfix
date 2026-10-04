"""Operadora de cartão (simulada)."""
from decimal import Decimal

from app.errors import PaymentDeclined

CARD_LIMIT = Decimal("5000.00")
DECLINED_CARD_SUFFIX = "0002"


def authorize(card_number: str, amount: Decimal) -> None:
    """Pede a autorização à operadora. Levanta PaymentDeclined se ela recusar."""
    if card_number.endswith(DECLINED_CARD_SUFFIX):
        raise PaymentDeclined("Pagamento recusado pela operadora")
    if amount > CARD_LIMIT:
        raise PaymentDeclined("Pagamento recusado pela operadora: limite insuficiente")
