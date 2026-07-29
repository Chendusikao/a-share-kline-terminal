from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Literal, cast
from uuid import uuid4

from app.api_models import (
    ErrorCode,
    ScanError,
    ScanRequest,
    ScanResult,
    ScanStatusResponse,
)
from app.indicators import MarketBar, calculate_indicators
from app.market_service import CandleService
from app.persistence import Database, ScanRepository
from app.scoring import MINIMUM_HISTORY, score_technical_analysis

DataStatus = Literal["network", "cache", "stale"]
Grade = Literal["弱", "偏弱", "中性", "偏强", "强"]


@dataclass(frozen=True, slots=True)
class ScanOutcome:
    score: float | None
    grade: Grade | None
    breakdown: dict[str, object]
    insights: list[dict[str, object]]
    data_status: DataStatus
    error_code: ErrorCode | None


class ScanService:
    def __init__(
        self,
        database: Database,
        candle_service: CandleService | None = None,
        *,
        analyze_symbol: Callable[[str, ScanRequest], ScanOutcome] | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        if candle_service is None and analyze_symbol is None:
            raise ValueError("a candle service or symbol analyzer is required")
        self._database = database
        self._candle_service = candle_service
        self._clock = now_provider or (lambda: datetime.now(UTC))
        self._analyze_symbol = analyze_symbol or self._analyze_from_candles
        self._database_lock = threading.RLock()
        self._workers = ThreadPoolExecutor(
            max_workers=3,
            thread_name_prefix="scan-symbol",
        )
        self._coordinator = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="scan-run",
        )
        with self._database_lock, self._database.session() as session:
            repository = ScanRepository(session)
            repository.recover_incomplete(completed_at=self._clock())
            repository.retain_latest(30)
            session.commit()

    def start(self, request: ScanRequest, *, market_date: date | None) -> str:
        config_hash = _request_hash(request)
        with self._database_lock, self._database.session() as session:
            repository = ScanRepository(session)
            if not request.force_refresh:
                duplicate = repository.find_duplicate(
                    market_date=market_date,
                    config_hash=config_hash,
                )
                if duplicate is not None:
                    return duplicate.id
            scan_id = str(uuid4())
            repository.create_run(
                scan_id=scan_id,
                market_date=market_date,
                config_hash=config_hash,
                symbols=request.symbols,
                created_at=self._clock(),
            )
            repository.retain_latest(30)
            session.commit()
        self._coordinator.submit(self._execute_run, scan_id, request)
        return scan_id

    def get_status(self, scan_id: str) -> ScanStatusResponse | None:
        with self._database_lock, self._database.session() as session:
            repository = ScanRepository(session)
            run = repository.get_run(scan_id)
            if run is None:
                return None
            rows = repository.results_for(scan_id)
            results: list[ScanResult] = []
            errors: list[ScanError] = []
            for row in rows:
                if row.data_status == "error":
                    code = cast(ErrorCode, row.error_code or "DATA_UNAVAILABLE")
                    errors.append(
                        ScanError(
                            symbol=row.symbol,
                            code=code,
                            message=_persisted_error_message(
                                row.breakdown_json,
                                code,
                            ),
                        )
                    )
                    continue
                if row.data_status == "pending":
                    continue
                previous = repository.previous_score(
                    before_run=run,
                    symbol=row.symbol,
                )
                score_change = (
                    row.score - previous
                    if row.score is not None and previous is not None
                    else None
                )
                results.append(
                    ScanResult.model_validate(
                        {
                            "symbol": row.symbol,
                            "score": row.score,
                            "grade": row.grade,
                            "breakdown": row.breakdown_json,
                            "insights": row.insights_json,
                            "dataStatus": row.data_status,
                            "errorCode": row.error_code,
                            "scoreChange": score_change,
                        }
                    )
                )
            completed_count = len(results) + len(errors)
            return ScanStatusResponse(
                scan_id=run.id,
                status=cast(
                    Literal["pending", "running", "completed", "failed"],
                    run.status,
                ),
                completed_count=completed_count,
                total_count=len(rows),
                market_date=run.market_date,
                results=results,
                errors=errors,
            )

    def latest_status(self) -> ScanStatusResponse | None:
        with self._database_lock, self._database.session() as session:
            latest = ScanRepository(session).latest_run()
        return self.get_status(latest.id) if latest is not None else None

    def shutdown(self) -> None:
        self._coordinator.shutdown(wait=True, cancel_futures=False)
        self._workers.shutdown(wait=True, cancel_futures=False)

    def _execute_run(self, scan_id: str, request: ScanRequest) -> None:
        with self._database_lock, self._database.session() as session:
            ScanRepository(session).mark_running(scan_id)
            session.commit()
        futures: dict[Future[ScanOutcome], str] = {
            self._workers.submit(self._with_retries, symbol, request): symbol
            for symbol in request.symbols
        }
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                outcome = future.result()
            except Exception as error:
                with self._database_lock, self._database.session() as session:
                    ScanRepository(session).save_error(
                        scan_id,
                        symbol,
                        "DATA_UNAVAILABLE",
                        message=str(error) or _error_message("DATA_UNAVAILABLE"),
                    )
                    session.commit()
            else:
                with self._database_lock, self._database.session() as session:
                    ScanRepository(session).save_result(
                        scan_id,
                        symbol,
                        score=outcome.score,
                        grade=outcome.grade,
                        breakdown_json=outcome.breakdown,
                        insights_json=outcome.insights,
                        data_status=outcome.data_status,
                        error_code=outcome.error_code,
                    )
                    session.commit()
        with self._database_lock, self._database.session() as session:
            repository = ScanRepository(session)
            repository.finish_run(scan_id, completed_at=self._clock())
            repository.retain_latest(30)
            session.commit()

    def _with_retries(self, symbol: str, request: ScanRequest) -> ScanOutcome:
        for attempt in range(3):
            try:
                return self._analyze_symbol(symbol, request)
            except Exception:
                if attempt == 2:
                    raise
        raise AssertionError("unreachable")

    def _analyze_from_candles(
        self,
        symbol: str,
        request: ScanRequest,
    ) -> ScanOutcome:
        assert self._candle_service is not None
        history_size = required_scan_history(request)
        candle_data = self._candle_service.get(
            symbol,
            now=self._clock(),
            force_refresh=request.force_refresh,
            history_limit=history_size,
        )
        candles = candle_data.candles[-history_size:]
        bars = [
            MarketBar(
                trade_date=item.trade_date,
                high=item.high,
                low=item.low,
                close=item.close,
                volume=item.volume,
            )
            for item in candles
        ]
        indicators = calculate_indicators(bars, request.indicator_config)
        analysis = score_technical_analysis(
            bars,
            indicators,
            request.score_weights,
        )
        status: DataStatus = (
            "stale"
            if candle_data.stale
            else "cache"
            if candle_data.from_cache
            else "network"
        )
        error_code: ErrorCode | None = (
            "INSUFFICIENT_HISTORY"
            if analysis.reason is not None
            and analysis.reason.startswith("insufficient_history:")
            else None
        )
        return ScanOutcome(
            score=analysis.total_score,
            grade=cast(Grade | None, analysis.grade),
            breakdown={
                _public_component(name): {
                    "score": component.score,
                    "weight": component.weight,
                    "evidence": [
                        {
                            "metric": evidence.metric,
                            "value": evidence.value,
                            "comparison": evidence.comparison,
                            "reference": evidence.reference,
                            "description": evidence.description,
                        }
                        for evidence in component.evidence
                    ],
                }
                for name, component in analysis.components.items()
            },
            insights=[
                {
                    "category": insight.category,
                    "direction": insight.direction,
                    "summary": insight.summary,
                    "severity": insight.severity,
                    "evidence": [
                        {
                            "metric": evidence.metric,
                            "value": evidence.value,
                            "comparison": evidence.comparison,
                            "reference": evidence.reference,
                            "description": evidence.description,
                        }
                        for evidence in insight.evidence
                    ],
                }
                for insight in analysis.insights
            ],
            data_status=status,
            error_code=error_code,
        )


def _request_hash(request: ScanRequest) -> str:
    payload = request.model_dump(
        mode="json",
        by_alias=True,
        exclude={"force_refresh"},
    )
    payload["symbols"] = sorted(request.symbols)
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def required_scan_history(request: ScanRequest) -> int:
    config = request.indicator_config
    return max(
        MINIMUM_HISTORY,
        config.macd.slow + config.macd.signal,
        config.rsi.period + 1,
        config.atr.period + 60,
    )


def _public_component(name: str) -> str:
    return "volumePrice" if name == "volume_price" else name


def _error_message(code: ErrorCode) -> str:
    messages = {
        "SYMBOL_NOT_FOUND": "未找到该股票代码。",
        "INVALID_CONFIG": "扫描配置无效。",
        "DATA_UNAVAILABLE": "行情数据暂时不可用，已重试两次。",
        "INSUFFICIENT_HISTORY": "有效交易日不足，暂时无法评分。",
        "SCAN_NOT_FOUND": "未找到扫描任务。",
    }
    return messages[code]


def _persisted_error_message(
    details: dict[str, object] | None,
    code: ErrorCode,
) -> str:
    if details is not None:
        message = details.get("errorMessage")
        if isinstance(message, str) and message.strip():
            return message
    return _error_message(code)
