from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.indicators import IndicatorConfig
from app.scoring import ComponentName, ScoreWeights

ErrorCode = Literal[
    "SYMBOL_NOT_FOUND",
    "INVALID_CONFIG",
    "DATA_UNAVAILABLE",
    "INSUFFICIENT_HISTORY",
    "SCAN_NOT_FOUND",
]
PublicComponentName = Literal[
    "trend",
    "momentum",
    "volumePrice",
    "position",
    "risk",
]
AnalysisRange = Literal["3m", "6m", "1y", "3y", "all"]
Symbol = Annotated[
    str,
    StringConstraints(strip_whitespace=True, pattern=r"^\d{6}$"),
]


def camelize_key(name: str) -> str:
    first, *rest = name.split("_")
    return first + "".join(part.capitalize() for part in rest)


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=camelize_key,
        allow_inf_nan=False,
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )


class HealthResponse(ApiModel):
    status: Literal["ok"]


class MarketStatusResponse(ApiModel):
    market_date: date | None
    status: Literal[
        "preOpen",
        "open",
        "middayBreak",
        "closed",
        "unavailable",
    ]
    is_open: bool
    is_trading_day: bool


class StockResponse(ApiModel):
    symbol: Symbol
    name: str
    exchange: Literal["SH", "SZ", "BJ"]


class StockSearchResponse(ApiModel):
    stocks: list[StockResponse]
    updated_at: date
    stale: bool


class AnalysisRequest(ApiModel):
    symbol: Symbol
    range: AnalysisRange = "3y"
    force_refresh: bool = False
    indicator_config: IndicatorConfig = Field(default_factory=IndicatorConfig)
    score_weights: ScoreWeights = Field(default_factory=ScoreWeights)


class CandleResponse(ApiModel):
    date: date
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    volume: float | None
    amount: float | None


class IndicatorSeriesResponse(ApiModel):
    values: list[float | None]
    reasons: list[str | None]


class IndicatorsResponse(ApiModel):
    dates: list[date]
    series: dict[str, IndicatorSeriesResponse]


class EvidenceResponse(ApiModel):
    metric: str
    value: float | None
    comparison: str
    reference: float | None
    description: str


class ComponentScoreResponse(ApiModel):
    score: float | None
    weight: float
    evidence: list[EvidenceResponse]


class ScoreResponse(ApiModel):
    available: bool
    reason: str | None
    total_score: int | None = Field(ge=0, le=100)
    grade: Literal["弱", "偏弱", "中性", "偏强", "强"] | None
    breakdown: dict[PublicComponentName, ComponentScoreResponse]
    effective_weights: dict[PublicComponentName, float]


class InsightResponse(ApiModel):
    category: ComponentName
    direction: Literal["偏多", "偏空", "中性", "风险"]
    summary: str
    severity: Literal["低", "中", "高"]
    evidence: list[EvidenceResponse]


class CacheResponse(ApiModel):
    status: Literal["network", "cache", "stale"]
    updated_at: date


class ApiWarning(ApiModel):
    code: ErrorCode
    message: str


class AnalysisResponse(ApiModel):
    stock: StockResponse
    market_date: date
    candles: list[CandleResponse]
    indicators: IndicatorsResponse
    score: ScoreResponse
    insights: list[InsightResponse]
    cache: CacheResponse
    warnings: list[ApiWarning]


class ValidationIssue(ApiModel):
    location: list[str | int]
    message: str
    type: str


class ErrorBody(ApiModel):
    code: ErrorCode
    message: str
    retryable: bool
    details: list[ValidationIssue] | None = None


class ErrorResponse(ApiModel):
    error: ErrorBody


class ScanRequest(ApiModel):
    symbols: list[Symbol] = Field(min_length=1, max_length=20)
    indicator_config: IndicatorConfig = Field(default_factory=IndicatorConfig)
    score_weights: ScoreWeights = Field(default_factory=ScoreWeights)
    force_refresh: bool = False

    @field_validator("symbols")
    @classmethod
    def require_unique_symbols(cls, symbols: list[str]) -> list[str]:
        if len(set(symbols)) != len(symbols):
            raise ValueError("scan symbols must be unique")
        return symbols


class ScanAcceptedResponse(ApiModel):
    scan_id: str


class ScanResult(ApiModel):
    symbol: Symbol
    score: float | None = Field(default=None, ge=0, le=100)
    grade: Literal["弱", "偏弱", "中性", "偏强", "强"] | None = None
    breakdown: dict[PublicComponentName, ComponentScoreResponse] | None = None
    insights: list[InsightResponse] | None = None
    data_status: Literal["network", "cache", "stale", "error"]
    error_code: ErrorCode | None = None


class ScanError(ApiModel):
    symbol: Symbol
    code: ErrorCode
    message: str


class ScanStatusResponse(ApiModel):
    scan_id: str
    status: Literal["pending", "running", "completed", "failed"]
    completed_count: int = Field(ge=0)
    total_count: int = Field(ge=0, le=20)
    market_date: date | None
    results: list[ScanResult]
    errors: list[ScanError]

    @model_validator(mode="after")
    def completed_cannot_exceed_total(self) -> ScanStatusResponse:
        if self.completed_count > self.total_count:
            raise ValueError("completed count cannot exceed total count")
        return self
