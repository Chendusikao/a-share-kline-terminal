from __future__ import annotations

import os
import time
from datetime import UTC, date, datetime, timedelta

import pandas as pd

from app.main import create_app
from app.persistence import Database


class OfflineGateway:
    def fetch_stock_list(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "code": ["000001", "600000"],
                "name": ["平安银行", "浦发银行"],
            }
        )

    def fetch_daily_candles(
        self,
        symbol: str,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        delay = float(os.getenv("A_SHARE_E2E_SCAN_DELAY_SECONDS", "0"))
        if delay > 0:
            time.sleep(delay)
        trading_days = _trading_days(120, ending=end_date or date(2026, 7, 30))
        closes = [
            10 + index * 0.03 + (0.04 if index % 3 == 0 else 0)
            for index in range(len(trading_days))
        ]
        return pd.DataFrame(
            {
                "日期": [day.isoformat() for day in trading_days],
                "开盘": [close - 0.05 for close in closes],
                "最高": [close + 0.12 for close in closes],
                "最低": [close - 0.12 for close in closes],
                "收盘": closes,
                "成交量": [100_000 + index * 100 for index in range(len(closes))],
                "成交额": [
                    close * (100_000 + index * 100)
                    for index, close in enumerate(closes)
                ],
            }
        )


def _trading_days(count: int, *, ending: date) -> list[date]:
    days: list[date] = []
    candidate = ending
    while len(days) < count:
        if candidate.weekday() < 5:
            days.append(candidate)
        candidate -= timedelta(days=1)
    return list(reversed(days))


database_path = os.getenv("A_SHARE_E2E_DATABASE_PATH")
database = Database(database_path if database_path else "sqlite+pysqlite:///:memory:")
app = create_app(
    database=database,
    market_gateway=OfflineGateway(),
    now_provider=lambda: datetime(2026, 7, 30, 8, 30, tzinfo=UTC),
)
