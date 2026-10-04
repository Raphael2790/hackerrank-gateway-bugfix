from datetime import date, datetime, timedelta


class Clock:
    """Hora atual da aplicação.

    Sem `now`, usa o relógio do sistema. Com `now`, fica parado nesse instante (é o que os testes usam)
    e só anda com `set` ou `advance`.
    """

    def __init__(self, now: datetime | None = None) -> None:
        self._now = now

    def now(self) -> datetime:
        if self._now is None:
            return datetime.now().replace(microsecond=0)
        return self._now

    def today(self) -> date:
        return self.now().date()

    def set(self, now: datetime) -> None:
        self._now = now

    def advance(self, **delta: float) -> None:
        self._now = self.now() + timedelta(**delta)
