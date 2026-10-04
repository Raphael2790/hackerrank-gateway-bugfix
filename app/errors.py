class NotFound(Exception):
    """Recurso inexistente (404)."""


class BadRequest(Exception):
    """Corpo ou parâmetros mal formados (400)."""


class PaymentError(Exception):
    """Base das falhas ao criar um pagamento."""


class InvalidPayment(PaymentError):
    """Os dados do pagamento violam uma regra de negócio (400)."""


class PaymentDeclined(PaymentError):
    """A operadora recusou o cartão (402)."""


class CardBlocked(PaymentError):
    """O antifraude bloqueou o cartão (429)."""


class InvalidTransition(Exception):
    """Operação não permitida no status atual do pagamento (409)."""


class RefundNotAllowed(Exception):
    """Estorno acima do valor disponível (409)."""


class RequestInProgress(Exception):
    """Já existe uma requisição em andamento com a mesma Idempotency-Key (409)."""


class IdempotencyConflict(Exception):
    """Idempotency-Key reutilizada com outro corpo (422)."""
