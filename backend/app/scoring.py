from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.indicators import IndicatorBundle, MarketBar

ComponentName = Literal[
    "trend",
    "momentum",
    "volume_price",
    "position",
    "risk",
]
Direction = Literal["偏多", "偏空", "中性", "风险"]
Severity = Literal["低", "中", "高"]

COMPONENT_NAMES: tuple[ComponentName, ...] = (
    "trend",
    "momentum",
    "volume_price",
    "position",
    "risk",
)
MINIMUM_HISTORY = 80


def _to_camel(name: str) -> str:
    first, *rest = name.split("_")
    return first + "".join(part.capitalize() for part in rest)


class ScoreWeights(BaseModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        allow_inf_nan=False,
        extra="forbid",
        populate_by_name=True,
    )

    trend: float = Field(default=35, ge=0)
    momentum: float = Field(default=25, ge=0)
    volume_price: float = Field(default=15, ge=0)
    position: float = Field(default=15, ge=0)
    risk: float = Field(default=10, ge=0)

    @model_validator(mode="after")
    def require_positive_total(self) -> ScoreWeights:
        raw = _raw_weights(self)
        if not any(value > 0 for value in raw.values()):
            raise ValueError("at least one score weight must be greater than zero")
        normalized = _decimal_percentages(raw)
        if any(raw[name] > 0 and normalized[name] == 0 for name in COMPONENT_NAMES):
            raise ValueError(
                "positive score weights are too different in scale to normalize"
            )
        return self


@dataclass(frozen=True, slots=True)
class Evidence:
    metric: str
    value: float | None
    comparison: str
    reference: float | None
    description: str


@dataclass(frozen=True, slots=True)
class ComponentScore:
    score: float | None
    weight: float
    evidence: list[Evidence]


@dataclass(frozen=True, slots=True)
class Insight:
    category: ComponentName
    direction: Direction
    summary: str
    severity: Severity
    evidence: list[Evidence]


@dataclass(frozen=True, slots=True)
class TechnicalAnalysis:
    available: bool
    reason: str | None
    total_score: int | None
    grade: str | None
    components: dict[ComponentName, ComponentScore]
    effective_weights: dict[ComponentName, float]
    insights: list[Insight]


@dataclass(frozen=True, slots=True)
class _ComputedComponent:
    score: float | None
    evidence: list[Evidence]


def normalize_weights(
    weights: ScoreWeights,
) -> dict[ComponentName, float]:
    raw = _raw_weights(weights)
    normalized = _decimal_percentages(raw)
    last_positive = next(name for name in reversed(COMPONENT_NAMES) if raw[name] > 0)
    normalized[last_positive] = 100.0 - sum(
        normalized[name] for name in COMPONENT_NAMES if name != last_positive
    )
    return normalized


def _raw_weights(weights: ScoreWeights) -> dict[ComponentName, float]:
    return {
        "trend": weights.trend,
        "momentum": weights.momentum,
        "volume_price": weights.volume_price,
        "position": weights.position,
        "risk": weights.risk,
    }


def _decimal_percentages(
    raw: Mapping[ComponentName, float],
) -> dict[ComponentName, float]:
    decimal_values = {name: Decimal.from_float(raw[name]) for name in COMPONENT_NAMES}
    total = sum(decimal_values.values(), start=Decimal(0))
    return {
        name: float(decimal_values[name] * Decimal(100) / total)
        for name in COMPONENT_NAMES
    }


def grade_for_score(score: int) -> str:
    if not 0 <= score <= 100:
        raise ValueError("score must be between 0 and 100")
    if score <= 34:
        return "弱"
    if score <= 44:
        return "偏弱"
    if score <= 55:
        return "中性"
    if score <= 65:
        return "偏强"
    return "强"


def score_technical_analysis(
    bars: Sequence[MarketBar],
    indicators: IndicatorBundle,
    weights: ScoreWeights | None = None,
) -> TechnicalAnalysis:
    ordered = sorted(bars, key=lambda bar: bar.trade_date)
    _validate_alignment(ordered, indicators)
    effective_weights = normalize_weights(weights or ScoreWeights())

    computed: dict[ComponentName, _ComputedComponent] = {
        "trend": _trend_component(ordered, indicators),
        "momentum": _momentum_component(indicators),
        "volume_price": _volume_price_component(ordered, indicators),
        "position": _position_component(ordered),
        "risk": _risk_component(ordered, indicators),
    }
    valid_trading_days = len({bar.trade_date for bar in ordered})
    duplicate_trade_dates = valid_trading_days != len(ordered)
    history_available = valid_trading_days >= MINIMUM_HISTORY
    missing = [name for name, item in computed.items() if item.score is None]
    available = history_available and not duplicate_trade_dates and not missing
    if duplicate_trade_dates:
        reason = "duplicate_trade_dates"
    elif not history_available:
        reason = f"insufficient_history:{MINIMUM_HISTORY}"
    elif missing:
        reason = f"missing_indicators:{','.join(missing)}"
    else:
        reason = None

    components = {
        name: ComponentScore(
            score=computed[name].score if available else None,
            weight=effective_weights[name],
            evidence=computed[name].evidence,
        )
        for name in COMPONENT_NAMES
    }
    total_score: int | None = None
    grade: str | None = None
    if available:
        weighted_total = sum(
            _required_score(computed[name]) * effective_weights[name] / 100
            for name in COMPONENT_NAMES
        )
        total_score = _round_half_up(weighted_total)
        grade = grade_for_score(total_score)

    insights = [
        _build_insight(
            name,
            computed[name],
            history_available=history_available,
            unavailable_reason=reason,
        )
        for name in COMPONENT_NAMES
    ]
    return TechnicalAnalysis(
        available=available,
        reason=reason,
        total_score=total_score,
        grade=grade,
        components=components,
        effective_weights=effective_weights,
        insights=insights,
    )


def _trend_component(
    bars: Sequence[MarketBar],
    indicators: IndicatorBundle,
) -> _ComputedComponent:
    close = _bar_value(bars, -1, "close")
    ma20 = _indicator_value(indicators, "ma_20", -1)
    ma60 = _indicator_value(indicators, "ma_60", -1)
    ma20_five_days_ago = _indicator_value(indicators, "ma_20", -6)
    if ma20 is None:
        ma20 = _rolling_mean(bars, 20, 0, "close")
    if ma60 is None:
        ma60 = _rolling_mean(bars, 60, 0, "close")
    if ma20_five_days_ago is None:
        ma20_five_days_ago = _rolling_mean(bars, 20, 5, "close")

    evidence = [
        _comparison_evidence("close_vs_ma20", close, ma20, "收盘价与 MA20"),
        _comparison_evidence("ma20_vs_ma60", ma20, ma60, "MA20 与 MA60"),
        _comparison_evidence(
            "ma20_five_day_slope",
            ma20,
            ma20_five_days_ago,
            "MA20 与五个交易日前",
        ),
    ]
    values = (close, ma20, ma60, ma20_five_days_ago)
    if any(value is None for value in values):
        return _ComputedComponent(None, evidence)
    assert close is not None
    assert ma20 is not None
    assert ma60 is not None
    assert ma20_five_days_ago is not None
    score = 50
    score += _signed_points(close, ma20, 20)
    score += _signed_points(ma20, ma60, 20)
    score += _signed_points(ma20, ma20_five_days_ago, 10)
    return _ComputedComponent(float(_clip(score)), evidence)


def _momentum_component(
    indicators: IndicatorBundle,
) -> _ComputedComponent:
    dif = _indicator_value(indicators, "macd_dif", -1)
    dea = _indicator_value(indicators, "macd_dea", -1)
    histogram = _indicator_value(indicators, "macd_histogram", -1)
    previous_histogram = _indicator_value(indicators, "macd_histogram", -2)
    rsi = _indicator_value(indicators, "rsi", -1)
    evidence = [
        _comparison_evidence("dif_vs_dea", dif, dea, "DIF 与 DEA"),
        _comparison_evidence(
            "macd_histogram_change",
            histogram,
            previous_histogram,
            "MACD 柱体与前一日",
        ),
        Evidence(
            metric="rsi_zone",
            value=rsi,
            comparison="区间",
            reference=None,
            description=_rsi_description(rsi),
        ),
    ]
    values = (dif, dea, histogram, previous_histogram, rsi)
    if any(value is None for value in values):
        return _ComputedComponent(None, evidence)
    assert dif is not None
    assert dea is not None
    assert histogram is not None
    assert previous_histogram is not None
    assert rsi is not None
    score = 50
    score += _signed_points(dif, dea, 20)
    score += _signed_points(histogram, previous_histogram, 15)
    if 55 <= rsi <= 70:
        score += 15
    elif 50 <= rsi < 55:
        score += 5
    elif 45 <= rsi < 50:
        score -= 5
    elif 30 <= rsi < 45:
        score -= 15
    return _ComputedComponent(float(_clip(score)), evidence)


def _volume_price_component(
    bars: Sequence[MarketBar],
    indicators: IndicatorBundle,
) -> _ComputedComponent:
    close = _bar_value(bars, -1, "close")
    previous_close = _bar_value(bars, -2, "close")
    volume = _bar_value(bars, -1, "volume")
    average_volume = _indicator_value(indicators, "volume_ma20", -1)
    if average_volume is None:
        average_volume = _rolling_mean(bars, 20, 0, "volume")
    volume_ratio = _safe_ratio(volume, average_volume)
    price_direction = _direction_label(close, previous_close)
    evidence = [
        Evidence(
            metric="daily_price_direction",
            value=close,
            comparison=price_direction,
            reference=previous_close,
            description=f"当日收盘相对前收为{price_direction}",
        ),
        Evidence(
            metric="volume_ratio",
            value=volume_ratio,
            comparison="相对",
            reference=1.0,
            description=_ratio_description(volume_ratio, "20 日均量"),
        ),
    ]
    if close is None or previous_close is None or volume_ratio is None:
        return _ComputedComponent(None, evidence)
    if volume_ratio >= 1.5:
        score = 80 if close > previous_close else 20 if close < previous_close else 50
    elif volume_ratio >= 0.7:
        score = 60 if close > previous_close else 40 if close < previous_close else 50
    else:
        score = 50
    return _ComputedComponent(float(score), evidence)


def _position_component(
    bars: Sequence[MarketBar],
) -> _ComputedComponent:
    close = _bar_value(bars, -1, "close")
    position_20 = _range_position(bars, 20, close)
    position_60 = _range_position(bars, 60, close)
    evidence = [
        Evidence(
            metric="position_20d",
            value=position_20,
            comparison="区间百分位",
            reference=None,
            description=_position_description(position_20, 20),
        ),
        Evidence(
            metric="position_60d",
            value=position_60,
            comparison="区间百分位",
            reference=None,
            description=_position_description(position_60, 60),
        ),
    ]
    if position_20 is None or position_60 is None:
        return _ComputedComponent(None, evidence)
    return _ComputedComponent((position_20 + position_60) / 2, evidence)


def _risk_component(
    bars: Sequence[MarketBar],
    indicators: IndicatorBundle,
) -> _ComputedComponent:
    current_close = _bar_value(bars, -1, "close")
    previous_close = _bar_value(bars, -2, "close")
    current_rsi = _indicator_value(indicators, "rsi", -1)
    current_atr = _indicator_value(indicators, "atr", -1)
    previous_atr = _indicator_value(indicators, "atr", -2)
    current_volume = _bar_value(bars, -1, "volume")
    average_volume = _indicator_value(indicators, "volume_ma20", -1)
    if average_volume is None:
        average_volume = _rolling_mean(bars, 20, 0, "volume")
    volume_ratio = _safe_ratio(current_volume, average_volume)
    current_atr_ratio = _safe_ratio(current_atr, current_close)
    historical_atr_ratios = _historical_atr_ratios(bars, indicators)
    atr_threshold = _percentile(historical_atr_ratios, 0.8)
    daily_move = (
        abs(current_close - previous_close)
        if current_close is not None and previous_close is not None
        else None
    )
    abnormal_threshold = previous_atr * 2 if previous_atr is not None else None

    triggers = {
        "rsi_extreme": (
            current_rsi is not None and (current_rsi > 70 or current_rsi < 30)
        ),
        "atr_percentile": (
            current_atr_ratio is not None
            and atr_threshold is not None
            and current_atr_ratio > atr_threshold
        ),
        "abnormal_daily_move": (
            daily_move is not None
            and abnormal_threshold is not None
            and daily_move > abnormal_threshold
        ),
        "volume_spike": volume_ratio is not None and volume_ratio >= 3,
    }
    evidence = [
        Evidence(
            "rsi_extreme",
            current_rsi,
            "超出 30–70" if triggers["rsi_extreme"] else "位于 30–70",
            None,
            _risk_description("RSI 极值", triggers["rsi_extreme"]),
        ),
        Evidence(
            "atr_percentile",
            current_atr_ratio,
            "高于" if triggers["atr_percentile"] else "未高于",
            atr_threshold,
            _risk_description("ATR 波动率 60 日 80 分位", triggers["atr_percentile"]),
        ),
        Evidence(
            "abnormal_daily_move",
            daily_move,
            "超过" if triggers["abnormal_daily_move"] else "未超过",
            abnormal_threshold,
            _risk_description(
                "单日绝对涨跌为前日 ATR 的两倍", triggers["abnormal_daily_move"]
            ),
        ),
        Evidence(
            "volume_spike",
            volume_ratio,
            "达到" if triggers["volume_spike"] else "未达到",
            3.0,
            _risk_description("成交量达到 20 日均量三倍", triggers["volume_spike"]),
        ),
    ]
    required = (
        current_rsi,
        current_atr_ratio,
        atr_threshold,
        daily_move,
        abnormal_threshold,
        volume_ratio,
    )
    if any(value is None for value in required):
        return _ComputedComponent(None, evidence)
    score = 100 - sum(25 for triggered in triggers.values() if triggered)
    return _ComputedComponent(float(_clip(score)), evidence)


def _build_insight(
    category: ComponentName,
    component: _ComputedComponent,
    *,
    history_available: bool,
    unavailable_reason: str | None,
) -> Insight:
    if unavailable_reason == "duplicate_trade_dates":
        return Insight(
            category,
            "中性",
            "行情数据包含重复交易日期（duplicate_trade_dates），不生成技术评分",
            "低",
            component.evidence,
        )
    if not history_available:
        risk_count = _risk_count(component.evidence) if category == "risk" else 0
        direction: Direction = "风险" if risk_count else "中性"
        severity: Severity = "中" if risk_count else "低"
        return Insight(
            category,
            direction,
            "有效交易日不足 80 日，仅展示当前可用指标证据",
            severity,
            component.evidence,
        )
    if component.score is None:
        return Insight(
            category,
            "中性",
            f"评分所需指标缺失（{unavailable_reason}），仅展示当前可用指标证据",
            "低",
            component.evidence,
        )

    score = component.score
    if category == "risk":
        risk_count = _risk_count(component.evidence)
        return Insight(
            category,
            "风险" if risk_count else "中性",
            f"识别到 {risk_count} 项技术波动风险"
            if risk_count
            else "未触发预设技术波动风险",
            "高" if risk_count >= 3 else "中" if risk_count else "低",
            component.evidence,
        )
    direction = "偏多" if score > 50 else "偏空" if score < 50 else "中性"
    distance = abs(score - 50)
    severity = "高" if distance >= 30 else "中" if distance >= 10 else "低"
    labels: Mapping[ComponentName, str] = {
        "trend": "趋势结构",
        "momentum": "动量结构",
        "volume_price": "量价确认",
        "position": "区间位置",
        "risk": "风险质量",
    }
    return Insight(
        category,
        direction,
        f"{labels[category]}评分为 {_display_number(score)}，方向为{direction}",
        severity,
        component.evidence,
    )


def _validate_alignment(
    bars: Sequence[MarketBar],
    indicators: IndicatorBundle,
) -> None:
    expected_dates = [bar.trade_date.isoformat() for bar in bars]
    if indicators.dates != expected_dates:
        raise ValueError("indicator dates must align with ordered market bars")
    for name, series in indicators.series.items():
        if len(series.values) != len(bars) or len(series.reasons) != len(bars):
            raise ValueError(f"indicator series length mismatch: {name}")


def _indicator_value(
    indicators: IndicatorBundle,
    name: str,
    index: int,
) -> float | None:
    series = indicators.series.get(name)
    if series is None or len(series.values) < abs(index):
        return None
    return _clean_number(series.values[index])


def _bar_value(
    bars: Sequence[MarketBar],
    index: int,
    field: Literal["close", "high", "low", "volume"],
) -> float | None:
    if len(bars) < abs(index):
        return None
    return _clean_number(getattr(bars[index], field))


def _rolling_mean(
    bars: Sequence[MarketBar],
    period: int,
    offset: int,
    field: Literal["close", "volume"],
) -> float | None:
    end = len(bars) - offset
    start = end - period
    if start < 0 or end <= 0:
        return None
    values = [_clean_number(getattr(bar, field)) for bar in bars[start:end]]
    if any(value is None for value in values):
        return None
    return sum(value for value in values if value is not None) / period


def _range_position(
    bars: Sequence[MarketBar],
    period: int,
    close: float | None,
) -> float | None:
    if close is None or len(bars) < period:
        return None
    window = bars[-period:]
    lows = [_clean_number(bar.low) for bar in window]
    highs = [_clean_number(bar.high) for bar in window]
    if any(value is None for value in [*lows, *highs]):
        return None
    low = min(value for value in lows if value is not None)
    high = max(value for value in highs if value is not None)
    if high == low:
        return 50.0
    return float(_clip((close - low) / (high - low) * 100))


def _historical_atr_ratios(
    bars: Sequence[MarketBar],
    indicators: IndicatorBundle,
) -> list[float]:
    if len(bars) < 61:
        return []
    values: list[float] = []
    for index in range(len(bars) - 61, len(bars) - 1):
        atr = _indicator_value(indicators, "atr", index - len(bars))
        close = _clean_number(bars[index].close)
        ratio = _safe_ratio(atr, close)
        if ratio is not None:
            values.append(ratio)
    return values if len(values) == 60 else []


def _percentile(values: Sequence[float], proportion: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * proportion
    lower_index = math.floor(position)
    upper_index = math.ceil(position)
    if lower_index == upper_index:
        return ordered[lower_index]
    fraction = position - lower_index
    return (
        ordered[lower_index] + (ordered[upper_index] - ordered[lower_index]) * fraction
    )


def _comparison_evidence(
    metric: str,
    value: float | None,
    reference: float | None,
    label: str,
) -> Evidence:
    comparison = _direction_label(value, reference)
    return Evidence(
        metric,
        value,
        comparison,
        reference,
        (
            f"{label}：{_display_number(value)}，"
            f"参照 {_display_number(reference)}（{comparison}）"
        ),
    )


def _direction_label(
    value: float | None,
    reference: float | None,
) -> str:
    if value is None or reference is None:
        return "数据不足"
    if value > reference:
        return "高于"
    if value < reference:
        return "低于"
    return "持平"


def _rsi_description(rsi: float | None) -> str:
    if rsi is None:
        return "RSI 数据不足"
    return f"RSI 为 {_display_number(rsi)}，处于 {_rsi_zone(rsi)}"


def _rsi_zone(rsi: float) -> str:
    if rsi > 70:
        return "70 以上极值区"
    if rsi >= 55:
        return "55–70 区间"
    if rsi >= 50:
        return "50–55 区间"
    if rsi >= 45:
        return "45–50 区间"
    if rsi >= 30:
        return "30–45 区间"
    return "30 以下极值区"


def _ratio_description(value: float | None, label: str) -> str:
    if value is None:
        return f"成交量相对{label}数据不足"
    return f"成交量为{label}的 {_display_number(value)} 倍"


def _position_description(value: float | None, period: int) -> str:
    if value is None:
        return f"{period} 日高低区间数据不足"
    return f"收盘价位于 {period} 日高低区间的 {_display_number(value)} 百分位"


def _risk_description(label: str, triggered: bool) -> str:
    return f"{label}风险{'已触发' if triggered else '未触发'}"


def _risk_count(evidence: Sequence[Evidence]) -> int:
    return sum(item.description.endswith("已触发") for item in evidence)


def _signed_points(value: float, reference: float, points: int) -> int:
    if value > reference:
        return points
    if value < reference:
        return -points
    return 0


def _safe_ratio(
    numerator: float | None,
    denominator: float | None,
) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return _clean_number(numerator / denominator)


def _clip(value: float) -> float:
    return min(100.0, max(0.0, value))


def _clean_number(value: float | int | None) -> float | None:
    if value is None:
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def _round_half_up(value: float) -> int:
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _required_score(component: _ComputedComponent) -> float:
    if component.score is None:
        raise ValueError("component score is unavailable")
    return component.score


def _display_number(value: float | None) -> str:
    if value is None:
        return "暂无"
    return f"{value:.4f}".rstrip("0").rstrip(".")
