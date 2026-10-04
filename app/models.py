from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

ZERO = Decimal("0.00")


class Method(str, Enum):
    PIX = "pix"
    DEBIT = "debit"
    CREDIT = "credit"


class Status(str, Enum):
    AUTHORIZED = "AUTHORIZED"
    CAPTURED = "CAPTURED"
    VOIDED = "VOIDED"
    EXPIRED = "EXPIRED"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED"
    REFUNDED = "REFUNDED"


@dataclass
class Merchant:
    id: int
    name: str


@dataclass
class Payment:
    id: int
    merchant_id: int
    method: Method
    amount: Decimal
    installments: int
    card_last4: str | None
    created_at: datetime
    status: Status = Status.AUTHORIZED
    captured_amount: Decimal = ZERO
    captured_at: datetime | None = None
    fee: Decimal = ZERO
    refunded_amount: Decimal = ZERO

    @property
    def net_amount(self) -> Decimal:
        return self.captured_amount - self.fee

    @property
    def refundable_amount(self) -> Decimal:
        return self.captured_amount - self.refunded_amount


@dataclass
class Receivable:
    """Lançamento na agenda do lojista: repasse de venda (positivo) ou débito de estorno (negativo)."""

    payment_id: int
    merchant_id: int
    installment: int | None
    amount: Decimal
    settle_date: date
    kind: str = "SALE"


@dataclass
class IdempotencyRecord:
    fingerprint: str
    payment_id: int | None = None  # None enquanto a requisição está em andamento
