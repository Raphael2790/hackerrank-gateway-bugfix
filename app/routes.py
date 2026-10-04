from datetime import date
from decimal import Decimal, InvalidOperation

from flask import Blueprint, Flask, current_app, jsonify, request

from app.clock import Clock
from app.errors import (
    BadRequest,
    CardBlocked,
    IdempotencyConflict,
    InvalidPayment,
    InvalidTransition,
    NotFound,
    PaymentDeclined,
    RefundNotAllowed,
    RequestInProgress,
)
from app.models import Merchant, Method, Payment, Receivable
from app.repository import Repository
from app.services import authorizations, settlement
from app.services import payments as payment_service
from app.services.payments import PaymentRequest

api = Blueprint("api", __name__)

CENT = Decimal("0.01")
METHODS = {method.value for method in Method}


def repo() -> Repository:
    return current_app.extensions["repo"]


def clock() -> Clock:
    return current_app.extensions["clock"]


def money(value: Decimal) -> str:
    return f"{value:.2f}"


def parse_money(value) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise BadRequest(f"Valor monetário inválido: {value!r}")
    try:
        amount = Decimal(str(value))
    except InvalidOperation:
        raise BadRequest(f"Valor monetário inválido: {value!r}") from None
    if not amount.is_finite() or amount <= 0 or amount.as_tuple().exponent < -2:
        raise BadRequest(f"Valor monetário inválido: {value!r} (use um valor positivo com até 2 casas)")
    return amount.quantize(CENT)


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise BadRequest(f"Data inválida: {value!r} (use AAAA-MM-DD)") from None


def body() -> dict:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise BadRequest("Corpo da requisição deve ser um JSON")
    return data


def optional_amount() -> Decimal | None:
    """Campo `amount` opcional de capturas e estornos (sem corpo = valor total)."""
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        raise BadRequest("Corpo da requisição deve ser um JSON")
    return parse_money(data["amount"]) if data.get("amount") is not None else None


def parse_payment_request(data: dict) -> PaymentRequest:
    merchant_id = data.get("merchant_id")
    if not isinstance(merchant_id, int) or isinstance(merchant_id, bool):
        raise BadRequest("merchant_id deve ser um inteiro")
    if data.get("amount") is None:
        raise BadRequest("amount é obrigatório")
    method = data.get("method")
    if not isinstance(method, str) or method not in METHODS:
        raise BadRequest("method deve ser pix, debit ou credit")
    installments = data.get("installments", 1)
    if not isinstance(installments, int) or isinstance(installments, bool):
        raise BadRequest("installments deve ser um inteiro")
    card_number = data.get("card_number")
    if card_number is not None and not isinstance(card_number, str):
        raise BadRequest("card_number deve ser uma string")
    capture = data.get("capture", True)
    if not isinstance(capture, bool):
        raise BadRequest("capture deve ser true ou false")
    return PaymentRequest(
        merchant_id=merchant_id,
        amount=parse_money(data["amount"]),
        method=Method(method),
        installments=installments,
        card_number=card_number,
        capture=capture,
        body=data,
    )


# ---------- serialização ----------

def merchant_json(merchant: Merchant) -> dict:
    return {"id": merchant.id, "name": merchant.name}


def payment_json(payment: Payment) -> dict:
    return {
        "id": payment.id,
        "merchant_id": payment.merchant_id,
        "method": payment.method.value,
        "amount": money(payment.amount),
        "installments": payment.installments,
        "card_last4": payment.card_last4,
        "status": payment.status.value,
        "created_at": payment.created_at.isoformat(),
        "captured_amount": money(payment.captured_amount),
        "captured_at": payment.captured_at.isoformat() if payment.captured_at else None,
        "fee": money(payment.fee),
        "net_amount": money(payment.net_amount),
        "refunded_amount": money(payment.refunded_amount),
    }


def receivable_json(receivable: Receivable) -> dict:
    return {
        "payment_id": receivable.payment_id,
        "installment": receivable.installment,
        "amount": money(receivable.amount),
        "settle_date": receivable.settle_date.isoformat(),
        "kind": receivable.kind,
    }


# ---------- lojistas ----------

@api.get("/merchants/<int:merchant_id>")
def get_merchant(merchant_id: int):
    return jsonify(merchant_json(repo().get_merchant(merchant_id)))


@api.get("/merchants/<int:merchant_id>/receivables")
def list_receivables(merchant_id: int):
    repo().get_merchant(merchant_id)
    entries = sorted(repo().receivables_of(merchant_id), key=lambda r: r.settle_date)
    return jsonify([receivable_json(r) for r in entries])


@api.get("/merchants/<int:merchant_id>/balance")
def get_balance(merchant_id: int):
    repo().get_merchant(merchant_id)
    raw_date = request.args.get("date")
    on = parse_date(raw_date) if raw_date else clock().today()
    available, pending = settlement.balance(repo(), merchant_id, on)
    return jsonify({
        "merchant_id": merchant_id,
        "date": on.isoformat(),
        "available": money(available),
        "pending": money(pending),
    })


# ---------- pagamentos ----------

@api.post("/payments")
def create_payment():
    payment_request = parse_payment_request(body())
    repo().get_merchant(payment_request.merchant_id)
    idempotency_key = request.headers.get("Idempotency-Key") or None
    payment, created = payment_service.create_payment(
        repo(), clock().now(), payment_request, idempotency_key
    )
    return jsonify(payment_json(payment)), (201 if created else 200)


@api.get("/payments/<int:payment_id>")
def get_payment(payment_id: int):
    return jsonify(payment_json(repo().get_payment(payment_id)))


@api.post("/payments/<int:payment_id>/capture")
def capture_payment(payment_id: int):
    payment = repo().get_payment(payment_id)
    authorizations.capture(repo(), payment, clock().now(), optional_amount())
    return jsonify(payment_json(payment))


@api.post("/payments/<int:payment_id>/void")
def void_payment(payment_id: int):
    payment = repo().get_payment(payment_id)
    authorizations.void(repo(), payment)
    return jsonify(payment_json(payment))


@api.post("/payments/<int:payment_id>/refund")
def refund_payment(payment_id: int):
    payment = repo().get_payment(payment_id)
    refunded = payment_service.refund(repo(), payment, clock().now(), optional_amount())
    return jsonify({"refunded": money(refunded), "payment": payment_json(payment)})


# ---------- rotinas ----------

@api.post("/jobs/expire-authorizations")
def expire_authorizations():
    expired = authorizations.expire_stale(repo(), clock().now())
    return jsonify({"expired": [payment.id for payment in expired]})


# ---------- erros ----------

ERROR_STATUS = {
    BadRequest: 400,
    InvalidPayment: 400,
    PaymentDeclined: 402,
    NotFound: 404,
    InvalidTransition: 409,
    RefundNotAllowed: 409,
    RequestInProgress: 409,
    IdempotencyConflict: 422,
    CardBlocked: 429,
}


def register_error_handlers(app: Flask) -> None:
    for exc_type, status in ERROR_STATUS.items():
        app.register_error_handler(
            exc_type, lambda e, status=status: (jsonify({"error": str(e)}), status)
        )
