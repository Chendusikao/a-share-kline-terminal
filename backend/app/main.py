from __future__ import annotations

import math
import os
from collections.abc import Callable
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Literal, Protocol, cast
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette import status

from app.api_models import (
    AnalysisRequest,
    AnalysisResponse,
    ApiWarning,
    CacheResponse,
    CandleResponse,
    ComponentScoreResponse,
    ErrorBody,
    ErrorCode,
    ErrorResponse,
    EvidenceResponse,
    HealthResponse,
    IndicatorSeriesResponse,
    IndicatorsResponse,
    InsightResponse,
    MarketStatusResponse,
    ScanAcceptedResponse,
    ScanRequest,
    ScanStatusResponse,
    ScoreResponse,
    StockResponse,
    StockSearchResponse,
    ValidationIssue,
    camelize_key,
)
from app.exchange_calendar import packaged_exchange_calendar
from app.indicators import (
    IndicatorBundle,
    MarketBar,
    calculate_indicators,
)
from app.market_gateway import AkshareGateway, DataUnavailableError
from app.market_service import (
    CandleData,
    CandleService,
    MarketGateway,
    StockCatalogService,
    StockSearchResult,
)
from app.persistence import CandleRecord, Database, StockRecord
from app.scan_service import ScanService
from app.scoring import (
    Evidence,
    TechnicalAnalysis,
    score_technical_analysis,
)

SHANGHAI = ZoneInfo("Asia/Shanghai")


class ExchangeCalendar(Protocol):
    def is_trading_day(self, day: date) -> bool: ...

    def latest_trading_day(self, on_or_before: date) -> date | None: ...


class ApiProblem(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        code: ErrorCode,
        message: str,
        retryable: bool = False,
        details: list[ValidationIssue] | None = None,
    ) -> None:
        self.status_code = status_code
        self.error = ErrorBody(
            code=code,
            message=message,
            retryable=retryable,
            details=details,
        )


def create_app(
    static_dir: Path | None = None,
    *,
    database: Database | None = None,
    market_gateway: MarketGateway | None = None,
    now_provider: Callable[[], datetime] | None = None,
    exchange_calendar: ExchangeCalendar | None = None,
) -> FastAPI:
    configured_database = database or _default_database()
    configured_database.create_schema()
    gateway = market_gateway or AkshareGateway()
    clock = now_provider or (lambda: datetime.now(UTC))
    calendar = exchange_calendar or packaged_exchange_calendar()
    stock_catalog = StockCatalogService(configured_database, gateway)
    candle_service = CandleService(configured_database, gateway)
    scan_service = ScanService(
        configured_database,
        candle_service,
        now_provider=lambda: _shanghai_now(clock()),
    )
    application = FastAPI(
        title="A 股 K 线终端",
        docs_url=None,
        redoc_url=None,
    )
    application.state.exchange_calendar = calendar

    @application.exception_handler(RequestValidationError)
    async def invalid_request(
        _request: Request,
        error: RequestValidationError,
    ) -> JSONResponse:
        details = [
            ValidationIssue(
                location=[
                    str(part) if not isinstance(part, int) else part
                    for part in item["loc"]
                ],
                message=item["msg"],
                type=item["type"],
            )
            for item in error.errors()
        ]
        return _error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="INVALID_CONFIG",
            message="请求参数或分析配置无效。",
            retryable=False,
            details=details,
        )

    @application.exception_handler(ApiProblem)
    async def api_problem(_request: Request, error: ApiProblem) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content=ErrorResponse(error=error.error).model_dump(
                mode="json",
                by_alias=True,
            ),
        )

    @application.exception_handler(DataUnavailableError)
    async def data_unavailable(
        _request: Request,
        _error: DataUnavailableError,
    ) -> JSONResponse:
        return _error_response(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="DATA_UNAVAILABLE",
            message="行情数据暂时不可用，请稍后重试。",
            retryable=True,
        )

    @application.get("/api/v1/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @application.get(
        "/api/v1/market/status",
        response_model=MarketStatusResponse,
    )
    def market_status() -> MarketStatusResponse:
        return _market_status(clock(), calendar)

    @application.get(
        "/api/v1/stocks/search",
        response_model=StockSearchResponse,
    )
    def search_stocks(
        q: str = Query(min_length=1),
        limit: int = Query(default=20, ge=1, le=20),
    ) -> StockSearchResponse:
        if not q.strip():
            raise ApiProblem(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code="INVALID_CONFIG",
                message="请求参数或分析配置无效。",
                details=[
                    ValidationIssue(
                        location=["query", "q"],
                        message="搜索关键词不能为空。",
                        type="value_error",
                    )
                ],
            )
        result = stock_catalog.search(
            q.strip(),
            limit=limit,
            now=_shanghai_now(clock()),
        )
        return _stock_search_response(result)

    @application.post(
        "/api/v1/analysis",
        response_model=AnalysisResponse,
    )
    def analyze(request: AnalysisRequest) -> AnalysisResponse:
        now = _shanghai_now(clock())
        catalog = stock_catalog.search(request.symbol, limit=20, now=now)
        stock = next(
            (item for item in catalog.stocks if item.symbol == request.symbol),
            None,
        )
        if stock is None:
            raise ApiProblem(
                status_code=status.HTTP_404_NOT_FOUND,
                code="SYMBOL_NOT_FOUND",
                message=f"未找到股票代码 {request.symbol}。",
            )
        candle_data = candle_service.get(
            request.symbol,
            now=now,
            force_refresh=request.force_refresh,
            range_name=request.range,
        )
        bars = [
            MarketBar(
                trade_date=candle.trade_date,
                high=candle.high,
                low=candle.low,
                close=candle.close,
                volume=candle.volume,
            )
            for candle in candle_data.candles
        ]
        indicators = calculate_indicators(bars, request.indicator_config)
        score = score_technical_analysis(
            bars,
            indicators,
            request.score_weights,
        )
        return _analysis_response(
            stock=stock,
            catalog=catalog,
            candle_data=candle_data,
            indicators=indicators,
            analysis=score,
        )

    @application.post(
        "/api/v1/scans",
        response_model=ScanAcceptedResponse,
        status_code=status.HTTP_202_ACCEPTED,
    )
    def start_scan(request: ScanRequest) -> ScanAcceptedResponse:
        local_now = _shanghai_now(clock())
        market = _market_status(local_now, calendar)
        if market.market_date is None:
            raise ApiProblem(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="DATA_UNAVAILABLE",
                message="市场交易日历暂时不可用。",
                retryable=False,
            )
        scan_id = scan_service.start(
            request,
            market_date=market.market_date,
        )
        return ScanAcceptedResponse(scan_id=scan_id)

    @application.get(
        "/api/v1/scans/latest",
        response_model=ScanStatusResponse,
    )
    def latest_scan() -> ScanStatusResponse:
        latest = scan_service.latest_status()
        if latest is None:
            raise _scan_not_found()
        return latest

    @application.get(
        "/api/v1/scans/{scan_id}",
        response_model=ScanStatusResponse,
    )
    def scan_status(scan_id: str) -> ScanStatusResponse:
        result = scan_service.get_status(scan_id)
        if result is None:
            raise _scan_not_found()
        return result

    application.router.add_event_handler("shutdown", scan_service.shutdown)

    frontend_dist = static_dir or Path(__file__).parents[2] / "frontend" / "dist"
    if frontend_dist.is_dir():
        application.mount(
            "/",
            StaticFiles(directory=frontend_dist, html=True),
            name="frontend",
        )

    return application


def _default_database() -> Database:
    configured_path = os.getenv("A_SHARE_DATABASE_PATH")
    path = (
        Path(configured_path)
        if configured_path
        else Path(__file__).parents[1] / "a_share_market.sqlite3"
    )
    return Database(path)


def _market_status(
    now: datetime,
    exchange_calendar: ExchangeCalendar | None = None,
) -> MarketStatusResponse:
    local_now = _shanghai_now(now)
    if exchange_calendar is None:
        return MarketStatusResponse(
            market_date=None,
            status="unavailable",
            is_open=False,
            is_trading_day=False,
        )
    market_date = exchange_calendar.latest_trading_day(local_now.date())
    if market_date is None:
        return MarketStatusResponse(
            market_date=None,
            status="unavailable",
            is_open=False,
            is_trading_day=False,
        )
    is_trading_day = exchange_calendar.is_trading_day(local_now.date())
    current_time = local_now.time().replace(tzinfo=None)
    if not is_trading_day:
        session: Literal["preOpen", "open", "middayBreak", "closed"] = "closed"
    elif current_time < time(9, 30):
        session = "preOpen"
    elif time(9, 30) <= current_time < time(11, 30):
        session = "open"
    elif time(11, 30) <= current_time < time(13):
        session = "middayBreak"
    elif time(13) <= current_time < time(15):
        session = "open"
    else:
        session = "closed"
    return MarketStatusResponse(
        market_date=market_date,
        status=session,
        is_open=session == "open",
        is_trading_day=is_trading_day,
    )


def _stock_search_response(result: StockSearchResult) -> StockSearchResponse:
    return StockSearchResponse(
        stocks=[_stock_response(stock) for stock in result.stocks],
        updated_at=result.updated_at.astimezone(SHANGHAI).date(),
        stale=result.stale,
    )


def _stock_response(stock: StockRecord) -> StockResponse:
    return StockResponse(
        symbol=stock.symbol,
        name=stock.name,
        exchange=cast(Literal["SH", "SZ", "BJ"], stock.exchange),
    )


def _analysis_response(
    *,
    stock: StockRecord,
    catalog: StockSearchResult,
    candle_data: CandleData,
    indicators: IndicatorBundle,
    analysis: TechnicalAnalysis,
) -> AnalysisResponse:
    warnings: list[ApiWarning] = []
    if catalog.stale:
        warnings.append(
            ApiWarning(
                code="DATA_UNAVAILABLE",
                message="股票列表刷新失败，当前使用缓存目录。",
            )
        )
    if candle_data.stale:
        warnings.append(
            ApiWarning(
                code="DATA_UNAVAILABLE",
                message="行情刷新失败，当前使用最近一次缓存数据。",
            )
        )
    if not analysis.available and analysis.reason == "insufficient_history:80":
        warnings.append(
            ApiWarning(
                code="INSUFFICIENT_HISTORY",
                message="有效交易日不足 80 日，评分暂不可用。",
            )
        )
    candles = [_candle_response(candle) for candle in candle_data.candles]
    return AnalysisResponse(
        stock=_stock_response(stock),
        market_date=candle_data.candles[-1].trade_date,
        candles=candles,
        indicators=_indicator_response(indicators),
        score=_score_response(analysis),
        insights=[
            InsightResponse(
                category=item.category,
                direction=item.direction,
                summary=item.summary,
                severity=item.severity,
                evidence=[_evidence_response(evidence) for evidence in item.evidence],
            )
            for item in analysis.insights
        ],
        cache=CacheResponse(
            status=(
                "stale"
                if candle_data.stale
                else "cache"
                if candle_data.from_cache
                else "network"
            ),
            updated_at=candle_data.updated_at.astimezone(SHANGHAI).date(),
        ),
        warnings=warnings,
    )


def _candle_response(candle: CandleRecord) -> CandleResponse:
    return CandleResponse(
        date=candle.trade_date,
        open=_finite_or_none(candle.open),
        high=_finite_or_none(candle.high),
        low=_finite_or_none(candle.low),
        close=_finite_or_none(candle.close),
        volume=_finite_or_none(candle.volume),
        amount=_finite_or_none(candle.amount),
    )


def _shanghai_now(now: datetime) -> datetime:
    aware_now = now if now.tzinfo is not None else now.replace(tzinfo=UTC)
    return aware_now.astimezone(SHANGHAI)


def _indicator_response(bundle: IndicatorBundle) -> IndicatorsResponse:
    return IndicatorsResponse(
        dates=[date.fromisoformat(value) for value in bundle.dates],
        series={
            _public_indicator_key(name): IndicatorSeriesResponse(
                values=[_finite_or_none(value) for value in series.values],
                reasons=series.reasons,
            )
            for name, series in bundle.series.items()
        },
    )


def _public_indicator_key(name: str) -> str:
    if name == "boll_mid":
        return "bollMiddle"
    return camelize_key(name)


def _score_response(analysis: TechnicalAnalysis) -> ScoreResponse:
    return ScoreResponse(
        available=analysis.available,
        reason=analysis.reason,
        total_score=_total_score_or_error(analysis.total_score),
        grade=cast(
            Literal["弱", "偏弱", "中性", "偏强", "强"] | None,
            analysis.grade,
        ),
        breakdown={
            _public_component_name(name): ComponentScoreResponse(
                score=_finite_or_none(component.score),
                weight=_required_finite(component.weight),
                evidence=[
                    _evidence_response(evidence) for evidence in component.evidence
                ],
            )
            for name, component in analysis.components.items()
        },
        effective_weights={
            _public_component_name(name): _required_finite(weight)
            for name, weight in analysis.effective_weights.items()
        },
    )


def _evidence_response(evidence: Evidence) -> EvidenceResponse:
    return EvidenceResponse(
        metric=evidence.metric,
        value=_finite_or_none(evidence.value),
        comparison=evidence.comparison,
        reference=_finite_or_none(evidence.reference),
        description=evidence.description,
    )


def _public_component_name(
    name: Literal["trend", "momentum", "volume_price", "position", "risk"],
) -> Literal["trend", "momentum", "volumePrice", "position", "risk"]:
    if name == "volume_price":
        return "volumePrice"
    return name


def _finite_or_none(value: float | int | None) -> float | None:
    if value is None:
        return None
    numeric = float(value)
    return numeric if math.isfinite(numeric) else None


def _required_finite(value: float | int) -> float:
    numeric = _finite_or_none(value)
    if numeric is None:
        raise DataUnavailableError("analysis produced a non-finite number")
    return numeric


def _total_score_or_error(value: int | None) -> int | None:
    if value is None:
        return None
    numeric = _required_finite(value)
    if not numeric.is_integer() or not 0 <= numeric <= 100:
        raise DataUnavailableError("analysis produced an invalid total score")
    return int(numeric)


def _error_response(
    *,
    status_code: int,
    code: ErrorCode,
    message: str,
    retryable: bool,
    details: list[ValidationIssue] | None = None,
) -> JSONResponse:
    response = ErrorResponse(
        error=ErrorBody(
            code=code,
            message=message,
            retryable=retryable,
            details=details,
        )
    )
    return JSONResponse(
        status_code=status_code,
        content=response.model_dump(mode="json", by_alias=True),
    )


def _scan_not_found() -> ApiProblem:
    return ApiProblem(
        status_code=status.HTTP_404_NOT_FOUND,
        code="SCAN_NOT_FOUND",
        message="未找到扫描任务。",
        retryable=False,
    )


app = create_app()
