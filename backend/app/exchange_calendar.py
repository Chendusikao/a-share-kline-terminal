from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache

# The bundled schedule is deliberately bounded. Outside this range the app
# reports the exchange calendar as unavailable instead of guessing.
CALENDAR_VALID_FROM = date(2024, 1, 1)
CALENDAR_VALID_THROUGH = date(2026, 12, 31)

# Published weekday closures for the Shanghai and Shenzhen exchanges. Weekend
# dates are omitted because exchanges do not follow compensating work weekends.
_WEEKDAY_CLOSURES = frozenset(
    date.fromisoformat(value)
    for value in (
        # 2024
        "2024-01-01",
        "2024-02-09",
        "2024-02-12",
        "2024-02-13",
        "2024-02-14",
        "2024-02-15",
        "2024-02-16",
        "2024-04-04",
        "2024-04-05",
        "2024-05-01",
        "2024-05-02",
        "2024-05-03",
        "2024-06-10",
        "2024-09-16",
        "2024-09-17",
        "2024-10-01",
        "2024-10-02",
        "2024-10-03",
        "2024-10-04",
        "2024-10-07",
        # 2025
        "2025-01-01",
        "2025-01-28",
        "2025-01-29",
        "2025-01-30",
        "2025-01-31",
        "2025-02-03",
        "2025-02-04",
        "2025-04-04",
        "2025-05-01",
        "2025-05-02",
        "2025-05-05",
        "2025-06-02",
        "2025-10-01",
        "2025-10-02",
        "2025-10-03",
        "2025-10-06",
        "2025-10-07",
        "2025-10-08",
        # 2026
        "2026-01-01",
        "2026-01-02",
        "2026-02-16",
        "2026-02-17",
        "2026-02-18",
        "2026-02-19",
        "2026-02-20",
        "2026-02-23",
        "2026-04-06",
        "2026-05-01",
        "2026-05-04",
        "2026-05-05",
        "2026-06-19",
        "2026-09-25",
        "2026-10-01",
        "2026-10-02",
        "2026-10-05",
        "2026-10-06",
        "2026-10-07",
    )
)


@dataclass(frozen=True, slots=True)
class LocalExchangeCalendar:
    valid_from: date = CALENDAR_VALID_FROM
    valid_through: date = CALENDAR_VALID_THROUGH
    weekday_closures: frozenset[date] = _WEEKDAY_CLOSURES

    def is_trading_day(self, day: date) -> bool:
        return (
            self.valid_from <= day <= self.valid_through
            and day.weekday() < 5
            and day not in self.weekday_closures
        )

    def latest_trading_day(self, on_or_before: date) -> date | None:
        if not self.valid_from <= on_or_before <= self.valid_through:
            return None
        candidate = on_or_before
        while candidate >= self.valid_from:
            if self.is_trading_day(candidate):
                return candidate
            candidate -= timedelta(days=1)
        return None


@lru_cache(maxsize=1)
def packaged_exchange_calendar() -> LocalExchangeCalendar:
    return LocalExchangeCalendar()
