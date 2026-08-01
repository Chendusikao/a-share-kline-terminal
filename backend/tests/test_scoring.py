from __future__ import annotations

import math
from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from app.indicators import IndicatorBundle, IndicatorSeries, MarketBar


def _bars(
    count: int = 80,
    *,
    close: float = 100,
    previous_close: float = 99,
    volume: float = 100,
    current_volume: float = 100,
    low: float = 90,
    high: float = 110,
) -> list[MarketBar]:
    first_date = date(2026, 1, 1)
    bars = [
        MarketBar(
            trade_date=first_date + timedelta(days=index),
            high=high,
            low=low,
            close=close,
            volume=volume,
        )
        for index in range(count)
    ]
    if count >= 2:
        bars[-2] = MarketBar(
            bars[-2].trade_date,
            high=max(high, previous_close),
            low=min(low, previous_close),
            close=previous_close,
            volume=volume,
        )
    if count:
        bars[-1] = MarketBar(
            bars[-1].trade_date,
            high=max(high, close),
            low=min(low, close),
            close=close,
            volume=current_volume,
        )
    return bars


def _series(
    count: int,
    current: float | None,
    *,
    previous: float | None = None,
    history: float | None = None,
) -> IndicatorSeries:
    values = [history] * count
    if count >= 2 and previous is not None:
        values[-2] = previous
    if count:
        values[-1] = current
    return IndicatorSeries(
        values=values,
        reasons=[
            None if value is not None else "insufficient_history" for value in values
        ],
    )


def _indicators(
    count: int = 80,
    *,
    dif: float | None = 2,
    dea: float | None = 1,
    histogram: float | None = 2,
    previous_histogram: float | None = 1,
    rsi: float | None = 60,
    atr: float | None = 1,
    previous_atr: float | None = 1,
    historical_atr: float | None = 1,
) -> IndicatorBundle:
    first_date = date(2026, 1, 1)
    ma_20 = _series(count, 90, previous=90, history=80)
    if count >= 6:
        ma_20.values[-6] = 80
    return IndicatorBundle(
        dates=[
            (first_date + timedelta(days=index)).isoformat() for index in range(count)
        ],
        series={
            "ma_20": ma_20,
            "ma_60": _series(count, 85),
            "macd_dif": _series(count, dif),
            "macd_dea": _series(count, dea),
            "macd_histogram": _series(
                count,
                histogram,
                previous=previous_histogram,
            ),
            "rsi": _series(count, rsi),
            "atr": _series(
                count,
                atr,
                previous=previous_atr,
                history=historical_atr,
            ),
            "volume_ma20": _series(count, 100),
        },
    )


def test_weights_validate_and_normalize_to_percentages() -> None:
    from app.scoring import ScoreWeights, normalize_weights

    defaults = normalize_weights(ScoreWeights())
    custom = normalize_weights(
        ScoreWeights(
            trend=1,
            momentum=1,
            volume_price=1,
            position=1,
            risk=0,
        )
    )

    assert defaults == {
        "trend": 35,
        "momentum": 25,
        "volume_price": 15,
        "position": 15,
        "risk": 10,
    }
    assert custom == {
        "trend": 25,
        "momentum": 25,
        "volume_price": 25,
        "position": 25,
        "risk": 0,
    }
    awkward = normalize_weights(
        ScoreWeights(
            trend=0.1,
            momentum=0.2,
            volume_price=0.3,
            position=0.4,
            risk=0.9,
        )
    )
    assert sum(awkward.values()) == 100
    for invalid in (
        {"trend": -1},
        {
            "trend": 0,
            "momentum": 0,
            "volume_price": 0,
            "position": 0,
            "risk": 0,
        },
        {"trend": math.inf},
        {"trend": math.nan},
    ):
        with pytest.raises(ValidationError):
            ScoreWeights.model_validate(invalid)


def test_large_finite_weights_normalize_without_aggregate_overflow() -> None:
    from app.scoring import ScoreWeights, normalize_weights

    normalized = normalize_weights(
        ScoreWeights(
            trend=1e308,
            momentum=1e308,
            volume_price=1e308,
            position=1e308,
            risk=1e308,
        )
    )

    assert normalized == {
        "trend": 20,
        "momentum": 20,
        "volume_price": 20,
        "position": 20,
        "risk": 20,
    }
    assert all(math.isfinite(value) for value in normalized.values())


def test_unrepresentable_positive_weight_share_is_rejected() -> None:
    from app.scoring import ScoreWeights

    with pytest.raises(ValidationError, match="too different"):
        ScoreWeights(
            trend=1e-200,
            momentum=1e200,
            volume_price=0,
            position=0,
            risk=0,
        )


def test_representable_subnormal_effective_share_remains_positive() -> None:
    from app.scoring import ScoreWeights, normalize_weights

    normalized = normalize_weights(
        ScoreWeights(
            trend=5e-324,
            momentum=1,
            volume_price=1,
            position=1,
            risk=1,
        )
    )

    assert normalized["trend"] > 0
    assert all(value > 0 for value in normalized.values())
    assert sum(normalized.values()) == 100


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (0, "弱"),
        (34, "弱"),
        (35, "偏弱"),
        (44, "偏弱"),
        (45, "中性"),
        (55, "中性"),
        (56, "偏强"),
        (65, "偏强"),
        (66, "强"),
        (100, "强"),
    ],
)
def test_grade_boundaries_are_fixed(score: int, expected: str) -> None:
    from app.scoring import grade_for_score

    assert grade_for_score(score) == expected


def test_five_component_scores_follow_the_documented_rules() -> None:
    from app.scoring import score_technical_analysis

    result = score_technical_analysis(
        _bars(current_volume=200),
        _indicators(),
    )

    assert result.available is True
    assert result.components["trend"].score == 100
    assert result.components["momentum"].score == 100
    assert result.components["volume_price"].score == 80
    assert result.components["position"].score == pytest.approx(50)
    assert result.components["risk"].score == 100
    assert result.total_score == 90
    assert result.grade == "强"


@pytest.mark.parametrize(
    ("rsi", "expected"),
    [
        (70, 100),
        (55, 100),
        (54.999, 90),
        (50, 90),
        (49.999, 80),
        (45, 80),
        (44.999, 70),
        (30, 70),
        (70.001, 85),
        (29.999, 85),
    ],
)
def test_momentum_rsi_boundaries_and_extremes(
    rsi: float,
    expected: float,
) -> None:
    from app.scoring import score_technical_analysis

    result = score_technical_analysis(_bars(), _indicators(rsi=rsi))

    assert result.components["momentum"].score == expected


@pytest.mark.parametrize(
    ("volume_ratio", "previous_close", "expected"),
    [
        (1.5, 99, 80),
        (1.5, 101, 20),
        (1.5, 100, 50),
        (0.7, 99, 60),
        (0.7, 101, 40),
        (0.7, 100, 50),
        (0.699, 99, 50),
    ],
)
def test_volume_price_boundaries(
    volume_ratio: float,
    previous_close: float,
    expected: float,
) -> None:
    from app.scoring import score_technical_analysis

    result = score_technical_analysis(
        _bars(
            previous_close=previous_close,
            volume=100,
            current_volume=volume_ratio * 100,
        ),
        _indicators(),
    )

    assert result.components["volume_price"].score == expected


def test_position_clips_each_window_percentile_and_handles_flat_ranges() -> None:
    from app.scoring import score_technical_analysis

    clipped = _bars(low=90, high=110, close=120, previous_close=100)
    clipped[-1] = MarketBar(
        clipped[-1].trade_date,
        high=120,
        low=90,
        close=120,
        volume=100,
    )
    flat = _bars(low=100, high=100, close=100, previous_close=100)

    assert (
        score_technical_analysis(clipped, _indicators()).components["position"].score
        == 100
    )
    assert (
        score_technical_analysis(flat, _indicators()).components["position"].score == 50
    )


def test_each_risk_trigger_deducts_twenty_five_points() -> None:
    from app.scoring import score_technical_analysis

    bars = _bars(previous_close=90, volume=100, current_volume=300)
    indicators = _indicators(
        rsi=71,
        atr=5,
        previous_atr=2,
        historical_atr=1,
    )

    result = score_technical_analysis(bars, indicators)
    risk = result.components["risk"]

    assert risk.score == 0
    assert len(risk.evidence) == 4
    assert {item.metric for item in risk.evidence} == {
        "rsi_extreme",
        "atr_percentile",
        "abnormal_daily_move",
        "volume_spike",
    }


def test_risk_trigger_comparison_boundaries_are_exact() -> None:
    from app.scoring import score_technical_analysis

    at_safe_edges = score_technical_analysis(
        _bars(previous_close=98, current_volume=299.9),
        _indicators(rsi=70, atr=1, previous_atr=1, historical_atr=1),
    )
    at_volume_trigger = score_technical_analysis(
        _bars(previous_close=98, current_volume=300),
        _indicators(rsi=30, atr=1, previous_atr=1, historical_atr=1),
    )

    assert at_safe_edges.components["risk"].score == 100
    assert at_volume_trigger.components["risk"].score == 75


def test_bearish_trend_and_momentum_rules_clip_at_zero() -> None:
    from app.scoring import score_technical_analysis

    indicators = _indicators(
        dif=-2,
        dea=-1,
        histogram=-2,
        previous_histogram=-1,
        rsi=30,
    )
    indicators.series["ma_20"].values[-1] = 110
    indicators.series["ma_20"].values[-6] = 120
    indicators.series["ma_60"].values[-1] = 115

    result = score_technical_analysis(_bars(), indicators)

    assert result.components["trend"].score == 0
    assert result.components["momentum"].score == 0


def test_custom_weights_are_used_after_normalization_and_total_is_rounded() -> None:
    from app.scoring import ScoreWeights, score_technical_analysis

    result = score_technical_analysis(
        _bars(current_volume=200),
        _indicators(),
        ScoreWeights(
            trend=1,
            momentum=1,
            volume_price=1,
            position=1,
            risk=0,
        ),
    )

    assert result.effective_weights == {
        "trend": 25,
        "momentum": 25,
        "volume_price": 25,
        "position": 25,
        "risk": 0,
    }
    assert result.total_score == 83


def test_insufficient_history_returns_no_scores_but_visible_available_evidence() -> (
    None
):
    from app.scoring import score_technical_analysis

    result = score_technical_analysis(
        _bars(79),
        _indicators(79),
    )

    assert result.available is False
    assert result.reason == "insufficient_history:80"
    assert result.total_score is None
    assert result.grade is None
    assert all(component.score is None for component in result.components.values())
    assert len(result.insights) == 5
    assert any(insight.evidence for insight in result.insights)


def test_duplicate_date_rejects_analysis_even_with_eighty_unique_dates() -> None:
    from app.scoring import score_technical_analysis

    bars = _bars(81)
    bars[1] = MarketBar(
        trade_date=bars[0].trade_date,
        high=bars[1].high,
        low=bars[1].low,
        close=bars[1].close,
        volume=bars[1].volume,
    )
    indicators = _indicators(81)
    indicators.dates[1] = indicators.dates[0]

    result = score_technical_analysis(bars, indicators)

    assert result.available is False
    assert result.reason == "duplicate_trade_dates"
    assert result.total_score is None
    assert result.grade is None
    assert all(component.score is None for component in result.components.values())
    assert all("重复交易日期" in insight.summary for insight in result.insights)


def test_missing_indicators_use_missing_indicator_insight_reason() -> None:
    from app.scoring import score_technical_analysis

    indicators = _indicators()
    del indicators.series["macd_dif"]

    result = score_technical_analysis(_bars(), indicators)
    momentum = next(
        insight for insight in result.insights if insight.category == "momentum"
    )

    assert result.reason == "missing_indicators:momentum"
    assert "指标缺失" in momentum.summary
    assert "交易日不足" not in momentum.summary


def test_insights_are_structured_visible_and_never_recommend_or_predict() -> None:
    from app.scoring import score_technical_analysis

    result = score_technical_analysis(_bars(), _indicators())

    assert [insight.category for insight in result.insights] == [
        "trend",
        "momentum",
        "volume_price",
        "position",
        "risk",
    ]
    assert all(
        insight.direction in {"偏多", "偏空", "中性", "风险"}
        for insight in result.insights
    )
    assert all(insight.severity in {"低", "中", "高"} for insight in result.insights)
    assert all(insight.summary for insight in result.insights)
    assert all(insight.evidence for insight in result.insights)
    rendered = " ".join(
        text
        for insight in result.insights
        for text in [
            insight.summary,
            *(evidence.description for evidence in insight.evidence),
        ]
    )
    assert "买入" not in rendered
    assert "卖出" not in rendered
    assert "收益" not in rendered
    assert "预测" not in rendered
    for insight in result.insights:
        for evidence in insight.evidence:
            assert evidence.value is None or math.isfinite(evidence.value)
            assert evidence.reference is None or math.isfinite(evidence.reference)
