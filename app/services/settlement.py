from datetime import date, datetime, timedelta
from decimal import ROUND_DOWN, Decimal

from app.models import ZERO, Method, Payment, Receivable
from app.repository import Repository
from app.services import fees

CENT = Decimal("0.01")
SATURDAY, SUNDAY = 5, 6
CREDIT_INTERVAL = timedelta(days=30)


def next_business_day(day: date) -> date:
    """O próprio dia, se for dia útil; senão, a segunda-feira seguinte."""
    while day.weekday() in (SATURDAY, SUNDAY):
        day += timedelta(days=1)
    return day


def settlement_dates(method: Method, captured_on: date, installments: int) -> list[date]:
    if method is Method.PIX:
        return [captured_on]
    if method is Method.DEBIT:
        return [next_business_day(captured_on + timedelta(days=1))]
    return [
        next_business_day(captured_on + CREDIT_INTERVAL * number)
        for number in range(1, installments + 1)
    ]


def split_evenly(total: Decimal, parts: int) -> list[Decimal]:
    """Divide em partes iguais arredondadas para baixo; os centavos que sobram vão para a primeira."""
    value = (total / parts).quantize(CENT, rounding=ROUND_DOWN)
    result = [value] * parts
    result[0] += total - value * parts
    return result


def register_capture(repo: Repository, payment: Payment, amount: Decimal, now: datetime) -> None:
    """Grava a captura, calcula a taxa e agenda os repasses do valor líquido."""
    payment.captured_amount = amount
    payment.captured_at = now
    payment.fee = fees.calculate_fee(amount, payment.method, payment.installments)
    dates = settlement_dates(payment.method, now.date(), payment.installments)
    amounts = split_evenly(payment.net_amount, len(dates))
    for number, (value, day) in enumerate(zip(amounts, dates), start=1):
        repo.receivables.append(Receivable(payment.id, payment.merchant_id, number, value, day))


def register_refund(repo: Repository, payment: Payment, amount: Decimal, now: datetime) -> None:
    """O estorno é debitado da agenda do lojista no mesmo dia."""
    repo.receivables.append(
        Receivable(payment.id, payment.merchant_id, None, -amount, now.date(), kind="REFUND")
    )


def balance(repo: Repository, merchant_id: int, on: date) -> tuple[Decimal, Decimal]:
    """(disponível, a receber) do lojista na data `on`."""
    entries = repo.receivables_of(merchant_id)
    available = sum((r.amount for r in entries if r.settle_date <= on), ZERO)
    pending = sum((r.amount for r in entries if r.settle_date > on), ZERO)
    return available, pending
