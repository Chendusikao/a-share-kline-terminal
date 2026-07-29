from __future__ import annotations

import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from datetime import date
from typing import Protocol, TypeVar

import akshare as ak
import pandas as pd


class DataUnavailableError(RuntimeError):
    code = "DATA_UNAVAILABLE"
    retryable = True


class MarketDataSource(Protocol):
    def fetch_stock_list(self) -> pd.DataFrame: ...

    def fetch_daily_candles(
        self,
        symbol: str,
        *,
        period: str,
        adjustment: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame: ...


class AkshareSource:
    def fetch_stock_list(self) -> pd.DataFrame:
        return ak.stock_info_a_code_name()

    def fetch_daily_candles(
        self,
        symbol: str,
        *,
        period: str,
        adjustment: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        return ak.stock_zh_a_hist(
            symbol=symbol,
            period=period,
            start_date=start_date,
            end_date=end_date,
            adjust=adjustment,
        )


T = TypeVar("T")


class AkshareGateway:
    def __init__(
        self,
        source: MarketDataSource | None = None,
        *,
        attempts: int = 3,
        timeout_seconds: float = 10,
        retry_delay_seconds: float = 0.2,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if attempts < 1:
            raise ValueError("attempts must be at least one")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._source = source or AkshareSource()
        self._attempts = attempts
        self._timeout_seconds = timeout_seconds
        self._retry_delay_seconds = retry_delay_seconds
        self._sleeper = sleeper

    def fetch_stock_list(self) -> pd.DataFrame:
        return self._with_retry(self._source.fetch_stock_list)

    def fetch_daily_candles(
        self,
        symbol: str,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        return self._with_retry(
            lambda: self._source.fetch_daily_candles(
                symbol,
                period="daily",
                adjustment="qfq",
                start_date=(
                    start_date.strftime("%Y%m%d")
                    if start_date is not None
                    else "19700101"
                ),
                end_date=(
                    end_date.strftime("%Y%m%d") if end_date is not None else "20500101"
                ),
            )
        )

    def _with_retry(self, operation: Callable[[], T]) -> T:
        last_error: BaseException | None = None
        for attempt in range(self._attempts):
            executor = ThreadPoolExecutor(max_workers=1)
            future = executor.submit(operation)
            try:
                return future.result(timeout=self._timeout_seconds)
            except (FutureTimeout, Exception) as error:
                last_error = error
                future.cancel()
            finally:
                executor.shutdown(wait=False, cancel_futures=True)

            if attempt + 1 < self._attempts and self._retry_delay_seconds:
                self._sleeper(self._retry_delay_seconds)

        raise DataUnavailableError(
            f"AKShare request failed after {self._attempts} attempts"
        ) from last_error
