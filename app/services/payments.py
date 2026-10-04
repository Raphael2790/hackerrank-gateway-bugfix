from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.errors import InvalidPayment, InvalidTransition, PaymentDeclined, RefundNotAllowed
from app.models import Method, Payment, Status
from app.repository import Repository
from app.services import antifraud, authorizations, idempotency, issuer, settlement

MAX_INSTALLMENTS = 12


@dataclass(frozen=True)
class PaymentRequest:
    merchant_id: int
    amount: Decimal
    method: Method
    installments: int
    card_number: str | None
    capture: bool
    body: dict  # corpo original da requisição, usado na idempotência


def create_payment(
    repo: Repository,
    now: datetime,
    request: PaymentRequest,
    idempotency_key: str | None = None,
) -> tuple[Payment, bool]:
    """Cria um pagamento. Devolve (pagamento, criado_agora); criado_agora é False numa repetição."""
    body_fingerprint = idempotency.fingerprint(request.body)
    record = None
    if idempotency_key:
        existing_id = idempotency.lookup(repo, request.merchant_id, idempotency_key, body_fingerprint)
        if existing_id is not None:
            return repo.get_payment(existing_id), False
        record = idempotency.reserve(repo, request.merchant_id, idempotency_key, body_fingerprint)

    try:
        payment = _process(repo, now, request)
    except PaymentDeclined:
        if record is not None:
            idempotency.release(repo, request.merchant_id, idempotency_key)
        raise

    if record is not None:
        idempotency.complete(record, payment.id)
    return payment, True


def _process(repo: Repository, now: datetime, request: PaymentRequest) -> Payment:
    _validate(request)
    if request.method is not Method.PIX:
        card = antifraud.card_key(request.card_number)
        antifraud.ensure_not_blocked(repo, card, now)
        try:
            issuer.authorize(request.card_number, request.amount)
        except PaymentDeclined:
            antifraud.register_decline(repo, card, now)
            raise

    payment = Payment(
        id=repo.next_payment_id(),
        merchant_id=request.merchant_id,
        method=request.method,
        amount=request.amount,
        installments=request.installments,
        card_last4=None if request.method is Method.PIX else request.card_number[-4:],
        created_at=now,
    )
    repo.payments[payment.id] = payment
    repo.pending_authorizations.append(payment)  # toda transação nasce como autorização
    if request.method is not Method.CREDIT or request.capture:
        authorizations.capture(repo, payment, now)
    return payment


def _validate(request: PaymentRequest) -> None:
    if request.method is Method.CREDIT:
        if not 1 <= request.installments <= MAX_INSTALLMENTS:
            raise InvalidPayment(f"Parcelas no crédito devem estar entre 1 e {MAX_INSTALLMENTS}")
    elif request.installments != 1:
        raise InvalidPayment(f"Pagamento {request.method.value} não pode ser parcelado")

    if request.method is not Method.PIX:
        card = request.card_number
        if card is None or len(card) != 16 or not card.isdigit():
            raise InvalidPayment("Número de cartão deve ter 16 dígitos")


def refund(repo: Repository, payment: Payment, now: datetime, amount: Decimal | None = None) -> Decimal:
    """Estorno total (sem valor) ou parcial de um pagamento capturado."""
    if payment.status not in (Status.CAPTURED, Status.PARTIALLY_REFUNDED):
        raise InvalidTransition(f"Pagamento {payment.status.value} não pode ser estornado")
    if amount is None:
        amount = payment.refundable_amount
    if amount > payment.refundable_amount:
        raise RefundNotAllowed(
            f"Valor do estorno excede o disponível (R$ {payment.refundable_amount})"
        )

    payment.refunded_amount += amount
    if payment.refundable_amount == 0:
        payment.status = Status.REFUNDED
    else:
        payment.status = Status.PARTIALLY_REFUNDED
    settlement.register_refund(repo, payment, amount, now)
    return amount
