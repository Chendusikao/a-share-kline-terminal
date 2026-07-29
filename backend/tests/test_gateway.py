from __future__ import annotations

import time

import pandas as pd
import pytest


class FlakySource:
    def __init__(self) -> None:
        self.attempts = 0
        self.request: tuple[str, str, str] | None = None

    def fetch_stock_list(self) -> pd.DataFrame:
        return pd.DataFrame()

    def fetch_daily_candles(
        self, symbol: str, *, period: str, adjustment: str
    ) -> pd.DataFrame:
        self.attempts += 1
        self.request = (symbol, period, adjustment)
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
        self, symbol: str, *, period: str, adjustment: str
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
    assert source.request == ("000001", "daily", "qfq")


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
