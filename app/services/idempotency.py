import hashlib
import json

from app.errors import IdempotencyConflict, RequestInProgress
from app.models import IdempotencyRecord
from app.repository import Repository


def fingerprint(body: dict) -> str:
    """Impressão digital do corpo da requisição (a ordem dos campos não importa)."""
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def lookup(repo: Repository, merchant_id: int, key: str, body_fingerprint: str) -> int | None:
    """Devolve o id do pagamento já criado com essa chave, ou None se a chave está livre."""
    record = repo.idempotency.get((merchant_id, key))
    if record is None:
        return None
    if record.fingerprint != body_fingerprint:
        raise IdempotencyConflict("Idempotency-Key já usada com outro corpo")
    if record.payment_id is None:
        raise RequestInProgress("Já existe uma requisição em andamento com essa Idempotency-Key")
    return record.payment_id


def reserve(repo: Repository, merchant_id: int, key: str, body_fingerprint: str) -> IdempotencyRecord:
    """Marca a chave como "em andamento", para que uma requisição repetida não cobre duas vezes."""
    record = IdempotencyRecord(body_fingerprint)
    repo.idempotency[(merchant_id, key)] = record
    return record


def complete(record: IdempotencyRecord, payment_id: int) -> None:
    record.payment_id = payment_id


def release(repo: Repository, merchant_id: int, key: str) -> None:
    """Libera a chave para uma nova tentativa."""
    repo.idempotency.pop((merchant_id, key), None)
