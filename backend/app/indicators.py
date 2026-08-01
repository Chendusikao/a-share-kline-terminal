from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Annotated

import pandas as pd
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

HexColor = Annotated[str, StringConstraints(pattern=r"^#[0-9A-Fa-f]{6}$")]


def _to_camel(name: str) -> str:
    first, *rest = name.split("_")
    return first + "".join(part.capitalize() for part in rest)


class StrictConfigModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        extra="forbid",
        populate_by_name=True,
    )


class MaConfig(StrictConfigModel):
    enabled: bool = True
    periods: list[int] = Field(
        default_factory=lambda: [5, 10, 20, 60],
        min_length=1,
        max_length=8,
    )
    colors: list[HexColor] = Field(
        default_factory=lambda: [
            "#F6C85F",
            "#6F4EED",
            "#42C2FF",
            "#EF6F6C",
            "#8BD17C",
            "#B6992D",
            "#5F6B6D",
            "#D45087",
        ],
        min_length=1,
        max_length=8,
    )

    @model_validator(mode="after")
    def validate_periods(self) -> MaConfig:
        if any(period < 2 or period > 250 for period in self.periods):
            raise ValueError("MA periods must be between 2 and 250")
        if len(set(self.periods)) != len(self.periods):
            raise ValueError("MA periods must be unique")
        return self


class MacdConfig(StrictConfigModel):
    enabled: bool = True
    fast: int = Field(default=12, ge=2, le=250)
    slow: int = Field(default=26, ge=2, le=250)
    signal: int = Field(default=9, ge=1, le=250)
    dif_color: HexColor = "#F6C85F"
    dea_color: HexColor = "#42C2FF"
    positive_color: HexColor = "#EF5350"
    negative_color: HexColor = "#26A69A"

    @model_validator(mode="after")
    def validate_order(self) -> MacdConfig:
        if self.fast >= self.slow:
            raise ValueError("MACD fast period must be less than slow period")
        return self


class RsiConfig(StrictConfigModel):
    enabled: bool = True
    period: int = Field(default=14, ge=2, le=100)
    color: HexColor = "#AB47BC"


class KdjConfig(StrictConfigModel):
    enabled: bool = True
    period: int = Field(default=9, ge=2, le=100)
    k_smoothing: int = Field(default=3, ge=1, le=20)
    d_smoothing: int = Field(default=3, ge=1, le=20)
    k_color: HexColor = "#F6C85F"
    d_color: HexColor = "#42C2FF"
    j_color: HexColor = "#AB47BC"


class BollConfig(StrictConfigModel):
    enabled: bool = True
    period: int = Field(default=20, ge=2, le=250)
    standard_deviations: float = Field(default=2, ge=0.5, le=5)
    middle_color: HexColor = "#F6C85F"
    upper_color: HexColor = "#EF5350"
    lower_color: HexColor = "#26A69A"


class AtrConfig(StrictConfigModel):
    enabled: bool = True
    period: int = Field(default=14, ge=2, le=100)
    color: HexColor = "#FF9800"


class VolumeMaConfig(StrictConfigModel):
    enabled: bool = True
    color: HexColor = "#42C2FF"


class IndicatorConfig(StrictConfigModel):
    ma: MaConfig = Field(default_factory=MaConfig)
    macd: MacdConfig = Field(default_factory=MacdConfig)
    rsi: RsiConfig = Field(default_factory=RsiConfig)
    kdj: KdjConfig = Field(default_factory=KdjConfig)
    boll: BollConfig = Field(default_factory=BollConfig)
    atr: AtrConfig = Field(default_factory=AtrConfig)
    volume_ma20: VolumeMaConfig = Field(default_factory=VolumeMaConfig)


@dataclass(frozen=True, slots=True)
class MarketBar:
    trade_date: date
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True, slots=True)
class IndicatorSeries:
    values: list[float | None]
    reasons: list[str | None]


@dataclass(frozen=True, slots=True)
class IndicatorBundle:
    dates: list[str]
    series: dict[str, IndicatorSeries]


def calculate_indicators(
    bars: Sequence[MarketBar],
    config: IndicatorConfig,
) -> IndicatorBundle:
    ordered = sorted(bars, key=lambda bar: bar.trade_date)
    _validate_bars(ordered)
    close = pd.Series([bar.close for bar in ordered], dtype="float64")
    high = pd.Series([bar.high for bar in ordered], dtype="float64")
    low = pd.Series([bar.low for bar in ordered], dtype="float64")
    volume = pd.Series([bar.volume for bar in ordered], dtype="float64")
    output: dict[str, IndicatorSeries] = {}

    for period in config.ma.periods:
        output[f"ma_{period}"] = _output_series(
            close.rolling(period, min_periods=period).mean(),
            period,
        )

    macd = config.macd
    fast_ema = close.ewm(
        span=macd.fast,
        adjust=False,
        min_periods=macd.fast,
    ).mean()
    slow_ema = close.ewm(
        span=macd.slow,
        adjust=False,
        min_periods=macd.slow,
    ).mean()
    dif = fast_ema - slow_ema
    dea = dif.ewm(
        span=macd.signal,
        adjust=False,
        min_periods=macd.signal,
    ).mean()
    histogram = (dif - dea) * 2
    output["macd_dif"] = _output_series(dif, macd.slow)
    macd_full_period = macd.slow + macd.signal - 1
    output["macd_dea"] = _output_series(dea, macd_full_period)
    output["macd_histogram"] = _output_series(
        histogram,
        macd_full_period,
    )

    delta = close.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    average_gain = _wilder_average(gains, config.rsi.period)
    average_loss = _wilder_average(losses, config.rsi.period)
    relative_strength = average_gain / average_loss
    rsi = 100 - (100 / (1 + relative_strength))
    rsi = rsi.mask((average_loss == 0) & (average_gain > 0), 100)
    rsi = rsi.mask((average_loss == 0) & (average_gain == 0), 50)
    output["rsi"] = _output_series(rsi, config.rsi.period + 1)

    rolling_high = high.rolling(
        config.kdj.period,
        min_periods=config.kdj.period,
    ).max()
    rolling_low = low.rolling(
        config.kdj.period,
        min_periods=config.kdj.period,
    ).min()
    price_range = rolling_high - rolling_low
    rsv = ((close - rolling_low) / price_range) * 100
    rsv = rsv.mask(price_range == 0, 50)
    k_values, d_values, j_values = _smooth_kdj(
        rsv,
        config.kdj.k_smoothing,
        config.kdj.d_smoothing,
    )
    output["kdj_k"] = _output_series(k_values, config.kdj.period)
    output["kdj_d"] = _output_series(d_values, config.kdj.period)
    output["kdj_j"] = _output_series(j_values, config.kdj.period)

    boll_middle = close.rolling(
        config.boll.period,
        min_periods=config.boll.period,
    ).mean()
    boll_deviation = close.rolling(
        config.boll.period,
        min_periods=config.boll.period,
    ).std(ddof=0)
    output["boll_mid"] = _output_series(boll_middle, config.boll.period)
    output["boll_upper"] = _output_series(
        boll_middle + boll_deviation * config.boll.standard_deviations,
        config.boll.period,
    )
    output["boll_lower"] = _output_series(
        boll_middle - boll_deviation * config.boll.standard_deviations,
        config.boll.period,
    )

    previous_close = close.shift(1)
    true_range = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = _wilder_average(true_range, config.atr.period)
    output["atr"] = _output_series(atr, config.atr.period)
    output["volume_ma20"] = _output_series(
        volume.rolling(20, min_periods=20).mean(),
        20,
    )

    return IndicatorBundle(
        dates=[bar.trade_date.isoformat() for bar in ordered],
        series=output,
    )


def _smooth_kdj(
    rsv: pd.Series,
    k_smoothing: int,
    d_smoothing: int,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    k_values: list[float] = []
    d_values: list[float] = []
    j_values: list[float] = []
    previous_k = 50.0
    previous_d = 50.0
    for value in rsv:
        if pd.isna(value):
            k_values.append(math.nan)
            d_values.append(math.nan)
            j_values.append(math.nan)
            continue
        current_k = ((k_smoothing - 1) * previous_k + float(value)) / k_smoothing
        current_d = ((d_smoothing - 1) * previous_d + current_k) / d_smoothing
        current_j = 3 * current_k - 2 * current_d
        k_values.append(current_k)
        d_values.append(current_d)
        j_values.append(current_j)
        previous_k = current_k
        previous_d = current_d
    return (
        pd.Series(k_values, dtype="float64"),
        pd.Series(d_values, dtype="float64"),
        pd.Series(j_values, dtype="float64"),
    )


def _wilder_average(values: pd.Series, period: int) -> pd.Series:
    result = [math.nan] * len(values)
    first_valid = next(
        (index for index, value in enumerate(values) if not pd.isna(value)),
        None,
    )
    if first_valid is None:
        return pd.Series(result, dtype="float64")
    initial_end = first_valid + period
    if initial_end > len(values):
        return pd.Series(result, dtype="float64")
    initial = float(values.iloc[first_valid:initial_end].mean())
    result[initial_end - 1] = initial
    previous = initial
    for index in range(initial_end, len(values)):
        value = float(values.iloc[index])
        if not math.isfinite(value):
            continue
        current = ((period - 1) * previous + value) / period
        result[index] = current
        previous = current
    return pd.Series(result, dtype="float64")


def _output_series(values: pd.Series, required: int) -> IndicatorSeries:
    clean_values: list[float | None] = []
    reasons: list[str | None] = []
    for value in values:
        numeric = float(value)
        if not math.isfinite(numeric):
            clean_values.append(None)
            reasons.append(f"insufficient_history:{required}")
        else:
            clean_values.append(numeric)
            reasons.append(None)
    return IndicatorSeries(clean_values, reasons)


def _validate_bars(bars: Sequence[MarketBar]) -> None:
    dates: set[date] = set()
    for bar in bars:
        if bar.trade_date in dates:
            raise ValueError("market bars must have unique trade dates")
        dates.add(bar.trade_date)
        values = (bar.high, bar.low, bar.close, bar.volume)
        if not all(math.isfinite(value) for value in values):
            raise ValueError("market bars must contain finite values")
        if bar.high < max(bar.low, bar.close):
            raise ValueError("market bar high must contain close and low")
        if bar.low > min(bar.high, bar.close):
            raise ValueError("market bar low must contain close and high")
