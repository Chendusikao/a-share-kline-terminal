from __future__ import annotations

import math
from datetime import date, timedelta
from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

if TYPE_CHECKING:
    from app.indicators import MarketBar


def test_indicator_config_has_documented_defaults() -> None:
    try:
        from app.indicators import IndicatorConfig
    except ModuleNotFoundError:
        pytest.fail("indicator configuration has not been implemented")

    config = IndicatorConfig()

    assert config.ma.periods == [5, 10, 20, 60]
    assert (config.macd.fast, config.macd.slow, config.macd.signal) == (12, 26, 9)
    assert config.rsi.period == 14
    assert (
        config.kdj.period,
        config.kdj.k_smoothing,
        config.kdj.d_smoothing,
    ) == (9, 3, 3)
    assert (config.boll.period, config.boll.standard_deviations) == (20, 2)
    assert config.atr.period == 14


def test_indicator_config_has_visible_defaults_and_validated_colors() -> None:
    from app.indicators import IndicatorConfig

    config = IndicatorConfig()

    assert config.ma.enabled is True
    assert config.ma.colors[:4] == [
        "#F6C85F",
        "#6F4EED",
        "#42C2FF",
        "#EF6F6C",
    ]
    assert config.macd.enabled is True
    assert config.macd.positive_color == "#EF5350"
    assert config.macd.negative_color == "#26A69A"
    assert config.rsi.enabled is True
    assert config.kdj.enabled is True
    assert config.boll.enabled is True
    assert config.atr.enabled is True
    assert config.volume_ma20.enabled is True

    customized = IndicatorConfig.model_validate(
        {
            "ma": {"enabled": False, "colors": ["#112233"]},
            "rsi": {"color": "#abcdef"},
            "volume_ma20": {"enabled": False, "color": "#AABBCC"},
        }
    )
    assert customized.ma.enabled is False
    assert customized.ma.colors == ["#112233"]
    assert customized.rsi.color == "#abcdef"
    assert customized.volume_ma20.enabled is False

    with pytest.raises(ValidationError):
        IndicatorConfig.model_validate({"atr": {"color": "orange"}})


@pytest.mark.parametrize(
    "overrides",
    [
        {"ma": {"periods": [1]}},
        {"ma": {"periods": [5, 5]}},
        {"ma": {"periods": [2, 3, 4, 5, 6, 7, 8, 9, 10]}},
        {"macd": {"fast": 26, "slow": 26, "signal": 9}},
        {"rsi": {"period": 101}},
        {"kdj": {"period": 1, "k_smoothing": 3, "d_smoothing": 3}},
        {"kdj": {"period": 9, "k_smoothing": 21, "d_smoothing": 3}},
        {"boll": {"period": 20, "standard_deviations": 0.4}},
        {"boll": {"period": 251, "standard_deviations": 2}},
        {"atr": {"period": 1}},
    ],
)
def test_indicator_config_rejects_out_of_range_or_ambiguous_parameters(
    overrides: dict[str, object],
) -> None:
    try:
        from app.indicators import IndicatorConfig
    except ModuleNotFoundError:
        pytest.fail("indicator configuration has not been implemented")

    with pytest.raises(ValidationError):
        IndicatorConfig.model_validate(overrides)


def test_indicator_config_rejects_custom_formula_fields() -> None:
    from app.indicators import IndicatorConfig

    with pytest.raises(ValidationError):
        IndicatorConfig.model_validate({"formula": "close * 2"})


def _bars(closes: list[float], *, flat_range: bool = False) -> list[MarketBar]:
    from app.indicators import MarketBar

    first_date = date(2026, 1, 1)
    return [
        MarketBar(
            trade_date=first_date + timedelta(days=index),
            high=close if flat_range else close + 1,
            low=close if flat_range else close - 1,
            close=close,
            volume=float(index + 1),
        )
        for index, close in enumerate(closes)
    ]


def test_ma_boll_atr_and_twenty_day_average_volume_match_hand_checked_values() -> None:
    from app.indicators import IndicatorConfig, calculate_indicators

    config = IndicatorConfig.model_validate(
        {
            "ma": {"periods": [2]},
            "macd": {"fast": 2, "slow": 3, "signal": 2},
            "rsi": {"period": 2},
            "kdj": {"period": 2, "k_smoothing": 3, "d_smoothing": 3},
            "boll": {"period": 3, "standard_deviations": 2},
            "atr": {"period": 2},
        }
    )

    short = calculate_indicators(_bars([1, 2, 3]), config)

    assert short.dates == ["2026-01-01", "2026-01-02", "2026-01-03"]
    assert short.series["ma_2"].values == [None, 1.5, 2.5]
    assert short.series["boll_mid"].values[-1] == pytest.approx(2, abs=1e-6)
    assert short.series["boll_upper"].values[-1] == pytest.approx(
        3.632993161855452, abs=1e-6
    )
    assert short.series["boll_lower"].values[-1] == pytest.approx(
        0.367006838144548, abs=1e-6
    )
    assert short.series["atr"].values == [None, 2, 2]
    assert short.series["volume_ma20"].values == [None, None, None]
    assert short.series["volume_ma20"].reasons[-1] == "insufficient_history:20"

    long = calculate_indicators(_bars([1.0] * 20), config)
    assert long.series["volume_ma20"].values[-1] == pytest.approx(10.5, abs=1e-6)


def test_macd_uses_daily_ema_and_a_share_double_histogram_convention() -> None:
    from app.indicators import IndicatorConfig, calculate_indicators

    config = IndicatorConfig.model_validate(
        {
            "ma": {"periods": [2]},
            "macd": {"fast": 2, "slow": 3, "signal": 2},
            "rsi": {"period": 2},
            "kdj": {"period": 2, "k_smoothing": 3, "d_smoothing": 3},
            "boll": {"period": 2, "standard_deviations": 2},
            "atr": {"period": 2},
        }
    )

    result = calculate_indicators(_bars([1, 2, 3, 4, 5, 6]), config)

    assert result.series["macd_dif"].values[2] == pytest.approx(
        0.305555555556, abs=1e-6
    )
    assert result.series["macd_dea"].values[3] == pytest.approx(
        0.364197530864, abs=1e-6
    )
    assert result.series["macd_histogram"].values[3] == pytest.approx(
        0.058641975309, abs=1e-6
    )


def test_rsi_and_kdj_handle_zero_losses_and_flat_ranges_without_nan() -> None:
    from app.indicators import IndicatorConfig, calculate_indicators

    config = IndicatorConfig.model_validate(
        {
            "ma": {"periods": [2]},
            "macd": {"fast": 2, "slow": 3, "signal": 2},
            "rsi": {"period": 2},
            "kdj": {"period": 2, "k_smoothing": 3, "d_smoothing": 3},
            "boll": {"period": 2, "standard_deviations": 2},
            "atr": {"period": 2},
        }
    )

    rising = calculate_indicators(_bars([1, 2, 3]), config)
    flat = calculate_indicators(_bars([5, 5, 5], flat_range=True), config)

    assert rising.series["rsi"].values[-1] == 100
    assert flat.series["kdj_k"].values[-1] == pytest.approx(50, abs=1e-6)
    assert flat.series["kdj_d"].values[-1] == pytest.approx(50, abs=1e-6)
    assert flat.series["kdj_j"].values[-1] == pytest.approx(50, abs=1e-6)


def test_rsi_and_atr_use_wilder_initial_average_and_smoothing() -> None:
    from app.indicators import (
        IndicatorConfig,
        MarketBar,
        calculate_indicators,
    )

    config = IndicatorConfig.model_validate(
        {
            "ma": {"periods": [2]},
            "macd": {"fast": 2, "slow": 3, "signal": 2},
            "rsi": {"period": 3},
            "kdj": {"period": 2, "k_smoothing": 3, "d_smoothing": 3},
            "boll": {"period": 2, "standard_deviations": 2},
            "atr": {"period": 3},
        }
    )
    rsi_result = calculate_indicators(_bars([1, 4, 4, 3, 5]), config)
    first_date = date(2026, 1, 1)
    atr_bars = [
        MarketBar(first_date, high=11, low=9, close=10, volume=1),
        MarketBar(first_date + timedelta(days=1), high=13, low=10, close=12, volume=1),
        MarketBar(first_date + timedelta(days=2), high=14, low=11, close=13, volume=1),
        MarketBar(first_date + timedelta(days=3), high=17, low=13, close=16, volume=1),
    ]
    atr_result = calculate_indicators(atr_bars, config)

    assert rsi_result.series["rsi"].values[3] == pytest.approx(75, abs=1e-6)
    assert rsi_result.series["rsi"].values[4] == pytest.approx(
        85.714285714286, abs=1e-6
    )
    assert atr_result.series["atr"].values[2] == pytest.approx(2.666666666667, abs=1e-6)
    assert atr_result.series["atr"].values[3] == pytest.approx(3.111111111111, abs=1e-6)


def test_insufficient_history_is_null_with_reason_and_never_nan() -> None:
    from app.indicators import IndicatorConfig, calculate_indicators

    result = calculate_indicators(_bars([10]), IndicatorConfig())

    for series in result.series.values():
        assert len(series.values) == 1
        assert len(series.reasons) == 1
        value = series.values[0]
        assert value is None or math.isfinite(value)
        if value is None:
            assert series.reasons[0] is not None
