from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Float,
    ForeignKey,
    String,
    create_engine,
    delete,
    or_,
    select,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    sessionmaker,
)
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


class StockModel(Base):
    __tablename__ = "stocks"

    symbol: Mapped[str] = mapped_column(String(6), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    exchange: Mapped[str] = mapped_column(String(8), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)


class DailyCandleModel(Base):
    __tablename__ = "daily_candles"

    symbol: Mapped[str] = mapped_column(String(6), primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date(), primary_key=True)
    open: Mapped[float] = mapped_column(Float(), nullable=False)
    high: Mapped[float] = mapped_column(Float(), nullable=False)
    low: Mapped[float] = mapped_column(Float(), nullable=False)
    close: Mapped[float] = mapped_column(Float(), nullable=False)
    volume: Mapped[float] = mapped_column(Float(), nullable=False)
    amount: Mapped[float | None] = mapped_column(Float(), nullable=True)
    adjustment: Mapped[str] = mapped_column(String(8), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)


class ScanRunModel(Base):
    __tablename__ = "scan_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    market_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(),
        nullable=True,
    )


class ScanResultModel(Base):
    __tablename__ = "scan_results"

    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("scan_runs.id", ondelete="CASCADE"),
        primary_key=True,
    )
    symbol: Mapped[str] = mapped_column(String(6), primary_key=True)
    score: Mapped[float | None] = mapped_column(Float(), nullable=True)
    grade: Mapped[str | None] = mapped_column(String(20), nullable=True)
    breakdown_json: Mapped[dict[str, object] | None] = mapped_column(
        JSON(),
        nullable=True,
    )
    insights_json: Mapped[list[dict[str, object]] | None] = mapped_column(
        JSON(),
        nullable=True,
    )
    data_status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(40), nullable=True)


@dataclass(frozen=True, slots=True)
class StockRecord:
    symbol: str
    name: str
    exchange: str
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class CandleRecord:
    symbol: str
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float | None
    adjustment: str
    fetched_at: datetime


class Database:
    def __init__(self, url: str | Path) -> None:
        database_url = str(url)
        if "://" not in database_url:
            database_url = f"sqlite+pysqlite:///{Path(database_url)}"
        engine_options: dict[str, object] = {}
        if database_url.endswith(":memory:"):
            engine_options["poolclass"] = StaticPool
            engine_options["connect_args"] = {"check_same_thread": False}
        self.engine: Engine = create_engine(database_url, **engine_options)
        self._sessions = sessionmaker(self.engine, expire_on_commit=False)

    def create_schema(self) -> None:
        Base.metadata.create_all(self.engine)

    def session(self) -> Session:
        return self._sessions()


class StockRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def replace_catalog(self, stocks: Iterable[StockRecord]) -> None:
        self._session.execute(delete(StockModel))
        self._session.add_all(
            StockModel(
                symbol=stock.symbol,
                name=stock.name,
                exchange=stock.exchange,
                updated_at=_as_naive_utc(stock.updated_at),
            )
            for stock in stocks
        )

    def search(self, query: str, limit: int) -> list[StockRecord]:
        pattern = f"%{query.strip()}%"
        statement = (
            select(StockModel)
            .where(
                or_(
                    StockModel.symbol.like(pattern),
                    StockModel.name.like(pattern),
                )
            )
            .order_by(StockModel.symbol)
            .limit(limit)
        )
        return [_stock_record(row) for row in self._session.scalars(statement)]

    def latest_updated_at(self) -> datetime | None:
        statement = (
            select(StockModel.updated_at)
            .order_by(StockModel.updated_at.desc())
            .limit(1)
        )
        value = self._session.scalar(statement)
        return _as_aware_utc(value) if value is not None else None


class CandleRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def replace_symbol(self, symbol: str, candles: Iterable[CandleRecord]) -> None:
        replacement = list(candles)
        if any(candle.symbol != symbol for candle in replacement):
            raise ValueError("all candles must belong to the replaced symbol")
        if any(candle.adjustment != "qfq" for candle in replacement):
            raise ValueError("only forward-adjusted daily candles are supported")
        self._session.execute(
            delete(DailyCandleModel).where(DailyCandleModel.symbol == symbol)
        )
        self._session.add_all(
            DailyCandleModel(
                symbol=candle.symbol,
                trade_date=candle.trade_date,
                open=candle.open,
                high=candle.high,
                low=candle.low,
                close=candle.close,
                volume=candle.volume,
                amount=candle.amount,
                adjustment=candle.adjustment,
                fetched_at=_as_naive_utc(candle.fetched_at),
            )
            for candle in replacement
        )

    def list_symbol(self, symbol: str) -> list[CandleRecord]:
        statement = (
            select(DailyCandleModel)
            .where(DailyCandleModel.symbol == symbol)
            .order_by(DailyCandleModel.trade_date)
        )
        return [_candle_record(row) for row in self._session.scalars(statement)]

    def latest_fetched_at(self, symbol: str) -> datetime | None:
        statement = (
            select(DailyCandleModel.fetched_at)
            .where(DailyCandleModel.symbol == symbol)
            .order_by(DailyCandleModel.fetched_at.desc())
            .limit(1)
        )
        value = self._session.scalar(statement)
        return _as_aware_utc(value) if value is not None else None


def _as_naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _stock_record(row: StockModel) -> StockRecord:
    return StockRecord(
        row.symbol,
        row.name,
        row.exchange,
        _as_aware_utc(row.updated_at),
    )


def _candle_record(row: DailyCandleModel) -> CandleRecord:
    return CandleRecord(
        row.symbol,
        row.trade_date,
        row.open,
        row.high,
        row.low,
        row.close,
        row.volume,
        row.amount,
        row.adjustment,
        _as_aware_utc(row.fetched_at),
    )
