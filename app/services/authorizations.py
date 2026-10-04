from datetime import datetime, timedelta
from decimal import Decimal

from app.errors import InvalidPayment, InvalidTransition
from app.models import Payment, Status
from app.repository import Repository
from app.services import settlement

AUTHORIZATION_TTL = timedelta(days=7)


def capture(repo: Repository, payment: Payment, now: datetime, amount: Decimal | None = None) -> Payment:
    """Captura total ou parcial. O que não for capturado é liberado no cartão do cliente."""
    _ensure_authorized(payment, "capturado")
    amount = payment.amount if amount is None else amount
    if amount > payment.amount:
        raise InvalidPayment("Valor da captura maior que o autorizado")
    _close(repo, payment, Status.CAPTURED)
    settlement.register_capture(repo, payment, amount, now)
    return payment


def void(repo: Repository, payment: Payment) -> Payment:
    """Cancela uma autorização que ainda não foi capturada."""
    _ensure_authorized(payment, "cancelado")
    _close(repo, payment, Status.VOIDED)
    return payment


def expire_stale(repo: Repository, now: datetime) -> list[Payment]:
    """Rotina diária: expira as autorizações pendentes há 7 dias ou mais."""
    expired = []
    for payment in repo.pending_authorizations:
        if now - payment.created_at >= AUTHORIZATION_TTL:
            _close(repo, payment, Status.EXPIRED)
            expired.append(payment)
    return expired


def _ensure_authorized(payment: Payment, action: str) -> None:
    if payment.status is not Status.AUTHORIZED:
        raise InvalidTransition(f"Pagamento {payment.status.value} não pode ser {action}")


def _close(repo: Repository, payment: Payment, status: Status) -> None:
    """Tira o pagamento da fila de autorizações pendentes e grava o novo status."""
    repo.pending_authorizations.remove(payment)
    payment.status = status
