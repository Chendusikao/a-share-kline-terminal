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
    update,
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


class ScanCandleModel(Base):
    __tablename__ = "scan_daily_candles"

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


@dataclass(frozen=True, slots=True)
class ScanRunRecord:
    id: str
    market_date: date | None
    config_hash: str
    status: str
    created_at: datetime
    completed_at: datetime | None


@dataclass(frozen=True, slots=True)
class ScanResultRecord:
    run_id: str
    symbol: str
    score: float | None
    grade: str | None
    breakdown_json: dict[str, object] | None
    insights_json: list[dict[str, object]] | None
    data_status: str
    error_code: str | None


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


class ScanCandleRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def replace_symbol(self, symbol: str, candles: Iterable[CandleRecord]) -> None:
        replacement = list(candles)
        if any(candle.symbol != symbol for candle in replacement):
            raise ValueError("all candles must belong to the replaced symbol")
        if any(candle.adjustment != "qfq" for candle in replacement):
            raise ValueError("only forward-adjusted daily candles are supported")
        self._session.execute(
            delete(ScanCandleModel).where(ScanCandleModel.symbol == symbol)
        )
        self._session.add_all(
            ScanCandleModel(
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
            select(ScanCandleModel)
            .where(ScanCandleModel.symbol == symbol)
            .order_by(ScanCandleModel.trade_date)
        )
        return [_scan_candle_record(row) for row in self._session.scalars(statement)]

    def latest_fetched_at(self, symbol: str) -> datetime | None:
        statement = (
            select(ScanCandleModel.fetched_at)
            .where(ScanCandleModel.symbol == symbol)
            .order_by(ScanCandleModel.fetched_at.desc())
            .limit(1)
        )
        value = self._session.scalar(statement)
        return _as_aware_utc(value) if value is not None else None


class ScanRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_run(
        self,
        *,
        scan_id: str,
        market_date: date | None,
        config_hash: str,
        symbols: Iterable[str],
        created_at: datetime,
    ) -> None:
        self._session.add(
            ScanRunModel(
                id=scan_id,
                market_date=market_date,
                config_hash=config_hash,
                status="pending",
                created_at=_as_naive_utc(created_at),
                completed_at=None,
            )
        )
        self._session.add_all(
            ScanResultModel(
                run_id=scan_id,
                symbol=symbol,
                score=None,
                grade=None,
                breakdown_json=None,
                insights_json=None,
                data_status="pending",
                error_code=None,
            )
            for symbol in symbols
        )

    def mark_running(self, scan_id: str) -> None:
        self._session.execute(
            update(ScanRunModel)
            .where(ScanRunModel.id == scan_id)
            .values(status="running")
        )

    def save_result(
        self,
        scan_id: str,
        symbol: str,
        *,
        score: float | None,
        grade: str | None,
        breakdown_json: dict[str, object],
        insights_json: list[dict[str, object]],
        data_status: str,
        error_code: str | None,
    ) -> None:
        self._session.execute(
            update(ScanResultModel)
            .where(
                ScanResultModel.run_id == scan_id,
                ScanResultModel.symbol == symbol,
            )
            .values(
                score=score,
                grade=grade,
                breakdown_json=breakdown_json,
                insights_json=insights_json,
                data_status=data_status,
                error_code=error_code,
            )
        )

    def save_error(
        self,
        scan_id: str,
        symbol: str,
        error_code: str,
        *,
        message: str,
    ) -> None:
        self._session.execute(
            update(ScanResultModel)
            .where(
                ScanResultModel.run_id == scan_id,
                ScanResultModel.symbol == symbol,
            )
            .values(
                data_status="error",
                error_code=error_code,
                breakdown_json={"errorMessage": message},
            )
        )

    def finish_run(self, scan_id: str, *, completed_at: datetime) -> None:
        self._session.execute(
            update(ScanRunModel)
            .where(ScanRunModel.id == scan_id)
            .values(
                status="completed",
                completed_at=_as_naive_utc(completed_at),
            )
        )

    def recover_incomplete(self, *, completed_at: datetime) -> int:
        incomplete = list(
            self._session.scalars(
                select(ScanRunModel.id).where(
                    ScanRunModel.status.in_(("pending", "running"))
                )
            )
        )
        if not incomplete:
            return 0
        self._session.execute(
            update(ScanRunModel)
            .where(ScanRunModel.id.in_(incomplete))
            .values(
                status="failed",
                completed_at=_as_naive_utc(completed_at),
            )
        )
        self._session.execute(
            update(ScanResultModel)
            .where(
                ScanResultModel.run_id.in_(incomplete),
                ScanResultModel.data_status == "pending",
            )
            .values(data_status="error", error_code="DATA_UNAVAILABLE")
        )
        return len(incomplete)

    def retain_latest(self, limit: int) -> None:
        if limit < 1:
            raise ValueError("scan retention limit must be positive")
        retained = (
            select(ScanRunModel.id)
            .order_by(
                ScanRunModel.created_at.desc(),
                ScanRunModel.id.desc(),
            )
            .limit(limit)
        )
        obsolete = list(
            self._session.scalars(
                select(ScanRunModel.id).where(ScanRunModel.id.not_in(retained))
            )
        )
        if not obsolete:
            return
        self._session.execute(
            delete(ScanResultModel).where(ScanResultModel.run_id.in_(obsolete))
        )
        self._session.execute(delete(ScanRunModel).where(ScanRunModel.id.in_(obsolete)))

    def get_run(self, scan_id: str) -> ScanRunRecord | None:
        row = self._session.get(ScanRunModel, scan_id)
        return _scan_run_record(row) if row is not None else None

    def latest_run(self) -> ScanRunRecord | None:
        row = self._session.scalar(
            select(ScanRunModel).order_by(
                ScanRunModel.created_at.desc(),
                ScanRunModel.id.desc(),
            )
        )
        return _scan_run_record(row) if row is not None else None

    def list_runs(self) -> list[ScanRunRecord]:
        rows = self._session.scalars(
            select(ScanRunModel).order_by(ScanRunModel.created_at)
        )
        return [_scan_run_record(row) for row in rows]

    def results_for(self, scan_id: str) -> list[ScanResultRecord]:
        rows = self._session.scalars(
            select(ScanResultModel)
            .where(ScanResultModel.run_id == scan_id)
            .order_by(ScanResultModel.symbol)
        )
        return [_scan_result_record(row) for row in rows]

    def find_duplicate(
        self,
        *,
        market_date: date | None,
        config_hash: str,
    ) -> ScanRunRecord | None:
        row = self._session.scalar(
            select(ScanRunModel)
            .where(
                ScanRunModel.market_date == market_date,
                ScanRunModel.config_hash == config_hash,
                ScanRunModel.status.in_(("pending", "running", "completed")),
            )
            .order_by(ScanRunModel.created_at.desc())
        )
        return _scan_run_record(row) if row is not None else None

    def previous_score(
        self,
        *,
        before_run: ScanRunRecord,
        symbol: str,
    ) -> float | None:
        return self._session.scalar(
            select(ScanResultModel.score)
            .join(ScanRunModel, ScanRunModel.id == ScanResultModel.run_id)
            .where(
                ScanRunModel.created_at < _as_naive_utc(before_run.created_at),
                ScanRunModel.status == "completed",
                ScanResultModel.symbol == symbol,
                ScanResultModel.score.is_not(None),
            )
            .order_by(ScanRunModel.created_at.desc())
            .limit(1)
        )


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


def _scan_candle_record(row: ScanCandleModel) -> CandleRecord:
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


def _scan_run_record(row: ScanRunModel) -> ScanRunRecord:
    return ScanRunRecord(
        id=row.id,
        market_date=row.market_date,
        config_hash=row.config_hash,
        status=row.status,
        created_at=_as_aware_utc(row.created_at),
        completed_at=(
            _as_aware_utc(row.completed_at) if row.completed_at is not None else None
        ),
    )


def _scan_result_record(row: ScanResultModel) -> ScanResultRecord:
    return ScanResultRecord(
        run_id=row.run_id,
        symbol=row.symbol,
        score=row.score,
        grade=row.grade,
        breakdown_json=row.breakdown_json,
        insights_json=row.insights_json,
        data_status=row.data_status,
        error_code=row.error_code,
    )
