from __future__ import annotations

import time

import pandas as pd
import pytest


class FlakySource:
    def __init__(self) -> None:
        self.attempts = 0
        self.request: tuple[str, str, str, str, str] | None = None

    def fetch_stock_list(self) -> pd.DataFrame:
        return pd.DataFrame()

    def fetch_daily_candles(
        self,
        symbol: str,
        *,
        period: str,
        adjustment: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        self.attempts += 1
        self.request = (symbol, period, adjustment, start_date, end_date)
        if self.attempts < 3:
            raise ConnectionError("temporary upstream failure")
        return pd.DataFrame([{"日期": "2026-07-29", "收盘": 10.5}])


class SlowSource:
    def __init__(self) -> None:
        self.attempts = 0

    def fetch_stock_list(self) -> pd.DataFrame:
        self.attempts += 1
        time.sleep(0.1)
        return pd.DataFrame()

    def fetch_daily_candles(
        self,
        symbol: str,
        *,
        period: str,
        adjustment: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        return pd.DataFrame()


def test_gateway_retries_transient_failure_and_requests_daily_qfq_data() -> None:
    try:
        from app.market_gateway import AkshareGateway
    except ModuleNotFoundError:
        pytest.fail("AKShare gateway has not been implemented")

    source = FlakySource()
    gateway = AkshareGateway(
        source=source,
        attempts=3,
        timeout_seconds=1,
        retry_delay_seconds=0,
    )

    result = gateway.fetch_daily_candles("000001")

    assert result.to_dict("records") == [{"日期": "2026-07-29", "收盘": 10.5}]
    assert source.attempts == 3
    assert source.request == (
        "000001",
        "daily",
        "qfq",
        "19700101",
        "20500101",
    )


def test_gateway_forwards_a_bounded_daily_history_window() -> None:
    from datetime import date

    from app.market_gateway import AkshareGateway

    source = FlakySource()
    gateway = AkshareGateway(
        source=source,
        attempts=3,
        timeout_seconds=1,
        retry_delay_seconds=0,
    )

    gateway.fetch_daily_candles(
        "000001",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 7, 30),
    )

    assert source.request == (
        "000001",
        "daily",
        "qfq",
        "20260101",
        "20260730",
    )


def test_gateway_turns_repeated_timeouts_into_retryable_data_unavailable() -> None:
    try:
        from app.market_gateway import AkshareGateway, DataUnavailableError
    except ModuleNotFoundError:
        pytest.fail("AKShare gateway has not been implemented")

    source = SlowSource()
    gateway = AkshareGateway(
        source=source,
        attempts=2,
        timeout_seconds=0.01,
        retry_delay_seconds=0,
    )

    with pytest.raises(DataUnavailableError) as captured:
        gateway.fetch_stock_list()

    assert captured.value.code == "DATA_UNAVAILABLE"
    assert captured.value.retryable is True
    assert source.attempts == 2


def test_real_akshare_source_fails_closed_when_network_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.market_gateway import AkshareGateway, AkshareSource, DataUnavailableError

    calls = 0

    def unexpected_network_call(_source: AkshareSource) -> pd.DataFrame:
        nonlocal calls
        calls += 1
        return pd.DataFrame()

    monkeypatch.setenv("A_SHARE_ALLOW_AKSHARE_NETWORK", "0")
    monkeypatch.setattr(AkshareSource, "fetch_stock_list", unexpected_network_call)

    with pytest.raises(DataUnavailableError, match="disabled"):
        AkshareGateway(attempts=1).fetch_stock_list()

    assert calls == 0
