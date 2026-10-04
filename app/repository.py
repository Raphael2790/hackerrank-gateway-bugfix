import itertools
from datetime import datetime

from app.errors import NotFound
from app.models import IdempotencyRecord, Merchant, Payment, Receivable

SEED_MERCHANTS = ["Loja Aurora", "Café Central"]


class Repository:
    """Armazenamento em memória. Uma instância por aplicação."""

    def __init__(self) -> None:
        self.merchants: dict[int, Merchant] = {}
        self.payments: dict[int, Payment] = {}
        self.receivables: list[Receivable] = []
        # Autorizações aguardando captura, na ordem em que foram criadas.
        self.pending_authorizations: list[Payment] = []
        self.idempotency: dict[tuple[int, str], IdempotencyRecord] = {}
        self.card_declines: dict[str, list[datetime]] = {}
        self.card_blocks: dict[str, datetime] = {}  # cartão -> bloqueado até
        self._merchant_ids = itertools.count(1)
        self._payment_ids = itertools.count(1)

    def seed(self) -> None:
        for name in SEED_MERCHANTS:
            merchant_id = next(self._merchant_ids)
            self.merchants[merchant_id] = Merchant(merchant_id, name)

    def next_payment_id(self) -> int:
        return next(self._payment_ids)

    def get_merchant(self, merchant_id: int) -> Merchant:
        return self._get(self.merchants, merchant_id, "Lojista")

    def get_payment(self, payment_id: int) -> Payment:
        return self._get(self.payments, payment_id, "Pagamento")

    def receivables_of(self, merchant_id: int) -> list[Receivable]:
        return [r for r in self.receivables if r.merchant_id == merchant_id]

    @staticmethod
    def _get(store: dict, key: int, label: str):
        try:
            return store[key]
        except KeyError:
            raise NotFound(f"{label} {key} não encontrado") from None
