from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Protocol

import pandas as pd

from app.market_gateway import DataUnavailableError
from app.persistence import (
    CandleRecord,
    CandleRepository,
    Database,
    StockRecord,
    StockRepository,
)


class MarketGateway(Protocol):
    def fetch_stock_list(self) -> pd.DataFrame: ...

    def fetch_daily_candles(self, symbol: str) -> pd.DataFrame: ...


@dataclass(frozen=True, slots=True)
class StockSearchResult:
    stocks: list[StockRecord]
    updated_at: datetime
    stale: bool


@dataclass(frozen=True, slots=True)
class CandleData:
    candles: list[CandleRecord]
    updated_at: datetime
    from_cache: bool
    stale: bool


class StockCatalogService:
    def __init__(self, database: Database, gateway: MarketGateway) -> None:
        self._database = database
        self._gateway = gateway

    def search(
        self,
        query: str,
        *,
        limit: int,
        now: datetime,
    ) -> StockSearchResult:
        if not 1 <= limit <= 20:
            raise ValueError("limit must be between 1 and 20")
        current_time = _aware_utc(now)
        stale = False

        with self._database.session() as session:
            repository = StockRepository(session)
            updated_at = repository.latest_updated_at()

        if updated_at is None or not _same_local_day(updated_at, now):
            try:
                frame = self._gateway.fetch_stock_list()
                records = _stock_records(frame, current_time)
                if not records:
                    raise DataUnavailableError(
                        "AKShare returned an empty stock catalog"
                    )
                with self._database.session() as session:
                    repository = StockRepository(session)
                    repository.replace_catalog(records)
                    session.commit()
                updated_at = current_time
            except DataUnavailableError:
                if updated_at is None:
                    raise
                stale = True

        with self._database.session() as session:
            stocks = StockRepository(session).search(query, limit)

        if updated_at is None:
            raise DataUnavailableError("stock catalog is unavailable")
        return StockSearchResult(stocks, updated_at, stale)


class CandleService:
    def __init__(self, database: Database, gateway: MarketGateway) -> None:
        self._database = database
        self._gateway = gateway

    def get(
        self,
        symbol: str,
        *,
        now: datetime,
        force_refresh: bool = False,
        range_name: str = "3y",
    ) -> CandleData:
        if range_name not in {"3m", "6m", "1y", "3y", "all"}:
            raise ValueError(f"unsupported candle range: {range_name}")
        current_time = _aware_utc(now)
        with self._database.session() as session:
            repository = CandleRepository(session)
            cached = repository.list_symbol(symbol)
            updated_at = repository.latest_fetched_at(symbol)

        is_fresh = updated_at is not None and _same_local_day(updated_at, now)
        if cached and is_fresh and not force_refresh:
            assert updated_at is not None
            return _slice_candle_data(
                CandleData(cached, updated_at, from_cache=True, stale=False),
                range_name,
            )

        try:
            frame = self._gateway.fetch_daily_candles(symbol)
            replacement = _candle_records(frame, symbol, current_time)
            if not replacement:
                raise DataUnavailableError("AKShare returned no valid candle data")
            with self._database.session() as session:
                repository = CandleRepository(session)
                repository.replace_symbol(symbol, replacement)
                session.commit()
            return _slice_candle_data(
                CandleData(
                    replacement,
                    current_time,
                    from_cache=False,
                    stale=False,
                ),
                range_name,
            )
        except DataUnavailableError:
            if cached and updated_at is not None:
                return _slice_candle_data(
                    CandleData(
                        cached,
                        updated_at,
                        from_cache=True,
                        stale=True,
                    ),
                    range_name,
                )
            raise


def _stock_records(frame: pd.DataFrame, updated_at: datetime) -> list[StockRecord]:
    code_column = _find_column(frame, "code", "代码")
    name_column = _find_column(frame, "name", "名称")
    records: dict[str, StockRecord] = {}
    for row in frame.to_dict("records"):
        raw_symbol = row.get(code_column)
        raw_name = row.get(name_column)
        if pd.isna(raw_symbol) or pd.isna(raw_name):
            continue
        symbol = str(raw_symbol).strip().split(".")[0].zfill(6)
        name = str(raw_name).strip()
        if len(symbol) != 6 or not symbol.isdigit() or not name:
            continue
        records[symbol] = StockRecord(
            symbol,
            name,
            _exchange_for(symbol),
            updated_at,
        )
    return sorted(records.values(), key=lambda stock: stock.symbol)


def _candle_records(
    frame: pd.DataFrame,
    symbol: str,
    fetched_at: datetime,
) -> list[CandleRecord]:
    columns = {
        "date": _find_column(frame, "日期", "date"),
        "open": _find_column(frame, "开盘", "open"),
        "high": _find_column(frame, "最高", "high"),
        "low": _find_column(frame, "最低", "low"),
        "close": _find_column(frame, "收盘", "close"),
        "volume": _find_column(frame, "成交量", "volume"),
    }
    amount_column = _find_column(frame, "成交额", "amount", required=False)
    records: dict[date, CandleRecord] = {}
    for row_number, row in enumerate(frame.to_dict("records"), start=1):
        try:
            trade_timestamp = pd.Timestamp(row[columns["date"]])
            if pd.isna(trade_timestamp):
                raise ValueError("trade date is missing")
            trade_date = trade_timestamp.date()
            open_value = _finite_float(row[columns["open"]])
            high_value = _finite_float(row[columns["high"]])
            low_value = _finite_float(row[columns["low"]])
            close_value = _finite_float(row[columns["close"]])
            volume_value = _finite_float(row[columns["volume"]])
        except (KeyError, TypeError, ValueError, OverflowError) as error:
            raise DataUnavailableError(
                f"AKShare returned a malformed candle at row {row_number}"
            ) from error
        if min(open_value, high_value, low_value, close_value) <= 0:
            raise DataUnavailableError(
                f"AKShare returned a non-positive price at row {row_number}"
            )
        if volume_value < 0:
            raise DataUnavailableError(
                f"AKShare returned negative volume at row {row_number}"
            )
        if high_value < max(open_value, close_value, low_value):
            raise DataUnavailableError(
                f"AKShare returned an invalid high at row {row_number}"
            )
        if low_value > min(open_value, close_value, high_value):
            raise DataUnavailableError(
                f"AKShare returned an invalid low at row {row_number}"
            )
        amount_value: float | None = None
        if amount_column is not None and not pd.isna(row.get(amount_column)):
            try:
                amount_value = _finite_float(row[amount_column])
            except (KeyError, TypeError, ValueError) as error:
                raise DataUnavailableError(
                    f"AKShare returned invalid amount at row {row_number}"
                ) from error
            if amount_value < 0:
                raise DataUnavailableError(
                    f"AKShare returned negative amount at row {row_number}"
                )
        if trade_date in records:
            raise DataUnavailableError(
                f"AKShare returned duplicate date at row {row_number}"
            )
        records[trade_date] = CandleRecord(
            symbol,
            trade_date,
            open_value,
            high_value,
            low_value,
            close_value,
            volume_value,
            amount_value,
            "qfq",
            fetched_at,
        )
    return [records[key] for key in sorted(records)]


def _find_column(
    frame: pd.DataFrame,
    *candidates: str,
    required: bool = True,
) -> str | None:
    for candidate in candidates:
        if candidate in frame.columns:
            return candidate
    if required:
        raise DataUnavailableError(
            f"AKShare response is missing column: {candidates[0]}"
        )
    return None


def _finite_float(value: object) -> float:
    result = float(value)  # type: ignore[arg-type]
    if not math.isfinite(result):
        raise ValueError("numeric market values must be finite")
    return result


def _exchange_for(symbol: str) -> str:
    if symbol.startswith(("4", "8")):
        return "BJ"
    if symbol.startswith(("5", "6", "9")):
        return "SH"
    return "SZ"


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _same_local_day(cached_at: datetime, now: datetime) -> bool:
    timezone = now.tzinfo or UTC
    return cached_at.astimezone(timezone).date() == now.date()


def _slice_candle_data(data: CandleData, range_name: str) -> CandleData:
    if range_name == "all" or not data.candles:
        return data
    latest = pd.Timestamp(data.candles[-1].trade_date)
    offsets = {
        "3m": pd.DateOffset(months=3),
        "6m": pd.DateOffset(months=6),
        "1y": pd.DateOffset(years=1),
        "3y": pd.DateOffset(years=3),
    }
    cutoff = (latest - offsets[range_name]).date()
    return CandleData(
        [candle for candle in data.candles if candle.trade_date >= cutoff],
        data.updated_at,
        data.from_cache,
        data.stale,
    )
