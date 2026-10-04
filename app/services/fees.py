from decimal import ROUND_HALF_UP, Decimal

from app.models import Method

CENT = Decimal("0.01")

# Taxa do lojista (MDR), em % sobre o valor capturado.
PIX_RATE = Decimal("0.99")
DEBIT_RATE = Decimal("1.99")
CREDIT_RATE = Decimal("2.99")  # crédito à vista
CREDIT_INSTALLMENTS_RATE = Decimal("3.99")  # crédito parcelado (2 a 12x)


def rate_for(method: Method, installments: int) -> Decimal:
    if method is Method.PIX:
        return PIX_RATE
    if method is Method.DEBIT:
        return DEBIT_RATE
    if installments == 1:
        return CREDIT_RATE
    return CREDIT_INSTALLMENTS_RATE


def calculate_fee(amount: Decimal, method: Method, installments: int) -> Decimal:
    return (amount * rate_for(method, installments) / 100).quantize(CENT, rounding=ROUND_HALF_UP)
