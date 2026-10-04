import hashlib
from datetime import datetime, timedelta

from app.errors import CardBlocked
from app.repository import Repository

MAX_DECLINES = 3
DECLINE_WINDOW = timedelta(minutes=10)
BLOCK_DURATION = timedelta(hours=1)


def card_key(card_number: str) -> str:
    """Identifica o cartão sem guardar o número."""
    return hashlib.sha256(card_number.encode()).hexdigest()


def ensure_not_blocked(repo: Repository, card: str, now: datetime) -> None:
    blocked_until = repo.card_blocks.get(card)
    if blocked_until is not None and now < blocked_until:
        raise CardBlocked(f"Cartão bloqueado pelo antifraude até {blocked_until:%d/%m %H:%M}")


def register_decline(repo: Repository, card: str, now: datetime) -> None:
    """Guarda a recusa e bloqueia o cartão se ele somar MAX_DECLINES recusas dentro da janela."""
    recent = [t for t in repo.card_declines.get(card, []) if now - t <= DECLINE_WINDOW]
    recent.append(now)
    repo.card_declines[card] = recent
    if len(recent) >= MAX_DECLINES:
        repo.card_blocks[card] = now + BLOCK_DURATION
