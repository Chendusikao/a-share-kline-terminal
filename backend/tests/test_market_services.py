from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from app.market_gateway import DataUnavailableError
from app.persistence import Database


class CatalogGateway:
    def __init__(self) -> None:
        self.catalog_calls = 0

    def fetch_stock_list(self) -> pd.DataFrame:
        self.catalog_calls += 1
        return pd.DataFrame(
            [
                {"code": "000001", "name": "平安银行"},
                {"code": "600000", "name": "浦发银行"},
            ]
        )

    def fetch_daily_candles(self, symbol: str) -> pd.DataFrame:
        raise AssertionError("candle fetch is not expected")


class CandleGateway:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.candle_calls = 0

    def fetch_stock_list(self) -> pd.DataFrame:
        if self.fail:
            raise DataUnavailableError("upstream unavailable")
        raise AssertionError("catalog fetch is not expected")

    def fetch_daily_candles(self, symbol: str) -> pd.DataFrame:
        self.candle_calls += 1
        if self.fail:
            raise DataUnavailableError("upstream unavailable")
        return pd.DataFrame(
            [
                {
                    "日期": "2026-07-28",
                    "开盘": 10.0,
                    "最高": 11.0,
                    "最低": 9.5,
                    "收盘": 10.5,
                    "成交量": 1000,
                    "成交额": 10500,
                },
                {
                    "日期": "2026-07-29",
                    "开盘": 10.5,
                    "最高": 12.0,
                    "最低": 10.0,
                    "收盘": 11.5,
                    "成交量": 1200,
                    "成交额": 13800,
                },
            ]
        )


class RangeGateway:
    def fetch_stock_list(self) -> pd.DataFrame:
        raise AssertionError("catalog fetch is not expected")

    def fetch_daily_candles(self, symbol: str) -> pd.DataFrame:
        rows = []
        for trade_date, close in (
            ("2022-07-29", 8.0),
            ("2025-07-28", 9.0),
            ("2025-07-29", 10.0),
            ("2026-07-29", 11.0),
        ):
            rows.append(
                {
                    "日期": trade_date,
                    "开盘": close,
                    "最高": close,
                    "最低": close,
                    "收盘": close,
                    "成交量": 1000,
                    "成交额": close * 1000,
                }
            )
        return pd.DataFrame(rows)


class PartiallyMalformedCandleGateway:
    def fetch_stock_list(self) -> pd.DataFrame:
        raise AssertionError("catalog fetch is not expected")

    def fetch_daily_candles(self, symbol: str) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "日期": "2026-07-30",
                    "开盘": 20.0,
                    "最高": 21.0,
                    "最低": 19.0,
                    "收盘": 20.5,
                    "成交量": 2000,
                    "成交额": 41000,
                },
                {
                    "日期": "2026-07-31",
                    "开盘": 21.0,
                    "最高": 22.0,
                    "最低": 20.0,
                    "收盘": float("nan"),
                    "成交量": 2200,
                    "成交额": 46200,
                },
            ]
        )


def test_stock_catalog_refreshes_once_per_day_and_searches_cached_names() -> None:
    try:
        from app.market_service import StockCatalogService
    except ModuleNotFoundError:
        pytest.fail("stock catalog service has not been implemented")

    database = Database("sqlite+pysqlite:///:memory:")
    database.create_schema()
    gateway = CatalogGateway()
    service = StockCatalogService(database, gateway)
    now = datetime(2026, 7, 29, 9, tzinfo=UTC)

    first = service.search("平安", limit=20, now=now)
    second = service.search("000001", limit=20, now=now + timedelta(hours=8))

    assert [stock.symbol for stock in first.stocks] == ["000001"]
    assert [stock.name for stock in second.stocks] == ["平安银行"]
    assert first.stale is False
    assert second.stale is False
    assert gateway.catalog_calls == 1


def test_stock_catalog_uses_and_marks_stale_cache_when_refresh_fails() -> None:
    try:
        from app.market_service import StockCatalogService
    except ModuleNotFoundError:
        pytest.fail("stock catalog service has not been implemented")

    database = Database("sqlite+pysqlite:///:memory:")
    database.create_schema()
    successful_gateway = CatalogGateway()
    service = StockCatalogService(database, successful_gateway)
    first_day = datetime(2026, 7, 28, 9, tzinfo=UTC)
    service.search("银行", limit=20, now=first_day)

    failing_gateway = CandleGateway(fail=True)
    degraded = StockCatalogService(database, failing_gateway).search(
        "银行",
        limit=20,
        now=first_day + timedelta(days=1),
    )

    assert [stock.symbol for stock in degraded.stocks] == ["000001", "600000"]
    assert degraded.stale is True
    assert degraded.updated_at == first_day


def test_candle_service_returns_stale_cache_on_failure_and_errors_without_cache() -> (
    None
):
    try:
        from app.market_service import CandleService
    except ModuleNotFoundError:
        pytest.fail("candle service has not been implemented")

    database = Database("sqlite+pysqlite:///:memory:")
    database.create_schema()
    first_day = datetime(2026, 7, 29, 16, tzinfo=UTC)
    fresh = CandleService(database, CandleGateway()).get(
        "000001",
        now=first_day,
    )

    assert [candle.trade_date.isoformat() for candle in fresh.candles] == [
        "2026-07-28",
        "2026-07-29",
    ]
    assert fresh.from_cache is False
    assert fresh.stale is False

    degraded = CandleService(database, CandleGateway(fail=True)).get(
        "000001",
        now=first_day + timedelta(days=1),
    )
    assert [candle.close for candle in degraded.candles] == [10.5, 11.5]
    assert degraded.from_cache is True
    assert degraded.stale is True
    assert degraded.updated_at == first_day

    empty_database = Database("sqlite+pysqlite:///:memory:")
    empty_database.create_schema()
    with pytest.raises(DataUnavailableError) as captured:
        CandleService(empty_database, CandleGateway(fail=True)).get(
            "000001",
            now=first_day,
        )
    assert captured.value.retryable is True


def test_candle_service_reuses_same_day_cache_without_network() -> None:
    try:
        from app.market_service import CandleService
    except ModuleNotFoundError:
        pytest.fail("candle service has not been implemented")

    database = Database("sqlite+pysqlite:///:memory:")
    database.create_schema()
    now = datetime(2026, 7, 29, 9, tzinfo=UTC)
    successful_gateway = CandleGateway()
    service = CandleService(database, successful_gateway)
    service.get("000001", now=now)

    failing_gateway = CandleGateway(fail=True)
    cached = CandleService(database, failing_gateway).get(
        "000001",
        now=now + timedelta(hours=8),
    )

    assert cached.from_cache is True
    assert cached.stale is False
    assert failing_gateway.candle_calls == 0


def test_candle_ranges_use_latest_market_date_and_default_to_three_years() -> None:
    from app.market_service import CandleService

    database = Database("sqlite+pysqlite:///:memory:")
    database.create_schema()
    now = datetime(2026, 7, 29, 16, tzinfo=UTC)
    service = CandleService(database, RangeGateway())

    default_range = service.get("000001", now=now)
    one_year = service.get("000001", now=now, range_name="1y")
    all_history = service.get("000001", now=now, range_name="all")

    assert [item.trade_date.isoformat() for item in default_range.candles] == [
        "2025-07-28",
        "2025-07-29",
        "2026-07-29",
    ]
    assert [item.trade_date.isoformat() for item in one_year.candles] == [
        "2025-07-29",
        "2026-07-29",
    ]
    assert len(all_history.candles) == 4

    with pytest.raises(ValueError, match="unsupported candle range"):
        service.get("000001", now=now, range_name="2y")


def test_malformed_refresh_preserves_complete_stale_candle_cache() -> None:
    from app.market_service import CandleService

    database = Database("sqlite+pysqlite:///:memory:")
    database.create_schema()
    cached_at = datetime(2026, 7, 29, 16, tzinfo=UTC)
    CandleService(database, CandleGateway()).get("000001", now=cached_at)

    result = CandleService(database, PartiallyMalformedCandleGateway()).get(
        "000001",
        now=cached_at + timedelta(days=1),
        range_name="all",
    )

    assert [candle.close for candle in result.candles] == [10.5, 11.5]
    assert result.updated_at == cached_at
    assert result.from_cache is True
    assert result.stale is True


def test_malformed_refresh_without_cache_is_data_unavailable() -> None:
    from app.market_service import CandleService

    database = Database("sqlite+pysqlite:///:memory:")
    database.create_schema()

    with pytest.raises(DataUnavailableError):
        CandleService(database, PartiallyMalformedCandleGateway()).get(
            "000001",
            now=datetime(2026, 7, 30, 16, tzinfo=UTC),
        )
