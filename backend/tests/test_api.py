from __future__ import annotations

import json
import math
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from typing import cast

import pandas as pd
import pytest
from pydantic import ValidationError
from starlette.testclient import TestClient

import app.main as main_module
from app.indicators import IndicatorBundle, MarketBar
from app.main import create_app
from app.market_gateway import DataUnavailableError
from app.persistence import Database
from app.scoring import ScoreWeights, TechnicalAnalysis, score_technical_analysis


class ApiGateway:
    def __init__(
        self,
        *,
        candle_count: int = 90,
        catalog_failure: bool = False,
        candle_failure: bool = False,
    ) -> None:
        self.catalog_calls = 0
        self.candle_calls = 0
        self._candle_count = candle_count
        self._catalog_failure = catalog_failure
        self._candle_failure = candle_failure

    def fetch_stock_list(self) -> pd.DataFrame:
        self.catalog_calls += 1
        if self._catalog_failure:
            raise DataUnavailableError("catalog unavailable")
        return pd.DataFrame(
            {
                "code": ["000001", "600000"],
                "name": ["平安银行", "浦发银行"],
            }
        )

    def fetch_daily_candles(
        self,
        symbol: str,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        self.candle_calls += 1
        if self._candle_failure:
            raise DataUnavailableError("candles unavailable")
        first_day = datetime(2026, 1, 1)
        closes = [10 + index * 0.05 for index in range(self._candle_count)]
        return pd.DataFrame(
            {
                "日期": [
                    (first_day + timedelta(days=index)).date().isoformat()
                    for index in range(self._candle_count)
                ],
                "开盘": [close - 0.1 for close in closes],
                "最高": [close + 0.2 for close in closes],
                "最低": [close - 0.2 for close in closes],
                "收盘": closes,
                "成交量": [1_000 + index for index in range(self._candle_count)],
                "成交额": [None]
                + [10_000 + index for index in range(1, self._candle_count)],
            }
        )


class FakeExchangeCalendar:
    def __init__(self, trading_days: set[date]) -> None:
        self._trading_days = trading_days

    def is_trading_day(self, day: date) -> bool:
        return day in self._trading_days

    def latest_trading_day(self, on_or_before: date) -> date | None:
        candidates = [day for day in self._trading_days if day <= on_or_before]
        return max(candidates, default=None)


def _client(
    gateway: ApiGateway | None = None,
    *,
    now: datetime | None = None,
    exchange_calendar: FakeExchangeCalendar | None = None,
    raise_server_exceptions: bool = True,
) -> TestClient:
    current_time = now or datetime(2026, 7, 30, 10, tzinfo=UTC)
    database = Database("sqlite+pysqlite:///:memory:")
    database.create_schema()
    if exchange_calendar is None:
        application = create_app(
            database=database,
            market_gateway=gateway or ApiGateway(),
            now_provider=lambda: current_time,
        )
    else:
        application = create_app(
            database=database,
            market_gateway=gateway or ApiGateway(),
            now_provider=lambda: current_time,
            exchange_calendar=exchange_calendar,
        )
    return TestClient(
        application,
        raise_server_exceptions=raise_server_exceptions,
    )


def _analysis_payload(**updates: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "symbol": "000001",
        "range": "all",
        "forceRefresh": False,
        "indicatorConfig": {},
        "scoreWeights": {},
    }
    payload.update(updates)
    return payload


def _assert_json_contains_only_finite_numbers(value: object) -> None:
    if isinstance(value, dict):
        for item in value.values():
            _assert_json_contains_only_finite_numbers(item)
    elif isinstance(value, list):
        for item in value:
            _assert_json_contains_only_finite_numbers(item)
    elif isinstance(value, float):
        assert math.isfinite(value)


def _assert_mapping_keys_are_camel_case(value: object) -> None:
    if isinstance(value, dict):
        assert all("_" not in key for key in value)
        for item in value.values():
            _assert_mapping_keys_are_camel_case(item)
    elif isinstance(value, list):
        for item in value:
            _assert_mapping_keys_are_camel_case(item)


def test_market_status_uses_ymd_dates_and_shanghai_session_state() -> None:
    response = _client(
        now=datetime(2026, 7, 30, 2, tzinfo=UTC),
        exchange_calendar=FakeExchangeCalendar({date(2026, 7, 30)}),
    ).get("/api/v1/market/status")

    assert response.status_code == 200
    assert response.json() == {
        "marketDate": "2026-07-30",
        "status": "open",
        "isOpen": True,
        "isTradingDay": True,
    }


def test_weekend_market_status_reports_the_latest_weekday_market_date() -> None:
    response = _client(
        now=datetime(2026, 8, 1, 2, tzinfo=UTC),
        exchange_calendar=FakeExchangeCalendar({date(2026, 7, 31)}),
    ).get("/api/v1/market/status")

    assert response.status_code == 200
    assert response.json() == {
        "marketDate": "2026-07-31",
        "status": "closed",
        "isOpen": False,
        "isTradingDay": False,
    }


def test_exchange_holiday_is_closed_even_when_it_falls_on_a_weekday() -> None:
    response = _client(
        now=datetime(2026, 10, 1, 2, tzinfo=UTC),
        exchange_calendar=FakeExchangeCalendar({date(2026, 9, 30)}),
    ).get("/api/v1/market/status")

    assert response.status_code == 200
    assert response.json() == {
        "marketDate": "2026-09-30",
        "status": "closed",
        "isOpen": False,
        "isTradingDay": False,
    }


def test_market_status_is_unavailable_without_an_exchange_calendar() -> None:
    response = _client(
        now=datetime(2026, 7, 30, 2, tzinfo=UTC),
    ).get("/api/v1/market/status")

    assert response.status_code == 200
    assert response.json() == {
        "marketDate": None,
        "status": "unavailable",
        "isOpen": False,
        "isTradingDay": False,
    }


def test_stock_search_returns_cached_catalog_metadata_and_camel_case_contract() -> None:
    gateway = ApiGateway()
    client = _client(gateway)

    response = client.get(
        "/api/v1/stocks/search",
        params={"q": "平安", "limit": 5},
    )

    assert response.status_code == 200
    assert response.json() == {
        "stocks": [
            {
                "symbol": "000001",
                "name": "平安银行",
                "exchange": "SZ",
            }
        ],
        "updatedAt": "2026-07-30",
        "stale": False,
    }
    assert gateway.catalog_calls == 1


def test_cache_dates_follow_shanghai_calendar_at_utc_day_boundary() -> None:
    client = _client(
        now=datetime(2026, 7, 30, 16, 30, tzinfo=UTC),
    )

    search = client.get(
        "/api/v1/stocks/search",
        params={"q": "000001", "limit": 5},
    )
    analysis = client.post("/api/v1/analysis", json=_analysis_payload())

    assert search.json()["updatedAt"] == "2026-07-31"
    assert analysis.json()["cache"]["updatedAt"] == "2026-07-31"


def test_analysis_returns_candles_indicators_score_insights_and_cache_state() -> None:
    gateway = ApiGateway()
    client = _client(gateway)

    response = client.post("/api/v1/analysis", json=_analysis_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["stock"] == {
        "symbol": "000001",
        "name": "平安银行",
        "exchange": "SZ",
    }
    assert body["marketDate"] == "2026-03-31"
    assert len(body["candles"]) == 90
    assert body["candles"][0] == {
        "date": "2026-01-01",
        "open": 9.9,
        "high": 10.2,
        "low": 9.8,
        "close": 10.0,
        "volume": 1000.0,
        "amount": None,
    }
    assert body["indicators"]["dates"][0] == "2026-01-01"
    assert set(body["indicators"]["series"]) >= {
        "ma20",
        "ma60",
        "macdDif",
        "macdDea",
        "macdHistogram",
        "rsi",
        "kdjK",
        "kdjD",
        "kdjJ",
        "bollMid",
        "bollUpper",
        "bollLower",
        "atr",
        "volumeMa20",
    }
    assert body["score"]["available"] is True
    assert 0 <= body["score"]["totalScore"] <= 100
    assert body["score"]["grade"] in {"弱", "偏弱", "中性", "偏强", "强"}
    assert set(body["score"]["breakdown"]) == {
        "trend",
        "momentum",
        "volumePrice",
        "position",
        "risk",
    }
    assert sum(body["score"]["effectiveWeights"].values()) == 100
    assert [item["category"] for item in body["insights"]] == [
        "trend",
        "momentum",
        "volume_price",
        "position",
        "risk",
    ]
    assert body["cache"] == {
        "status": "network",
        "updatedAt": "2026-07-30",
    }
    assert body["warnings"] == []
    assert "NaN" not in response.text
    _assert_json_contains_only_finite_numbers(body)
    _assert_mapping_keys_are_camel_case(body)


def test_analysis_reuses_fresh_cache_and_force_refresh_bypasses_it() -> None:
    gateway = ApiGateway()
    client = _client(gateway)

    first = client.post("/api/v1/analysis", json=_analysis_payload())
    cached = client.post("/api/v1/analysis", json=_analysis_payload())
    refreshed = client.post(
        "/api/v1/analysis",
        json=_analysis_payload(forceRefresh=True),
    )

    assert first.json()["cache"]["status"] == "network"
    assert cached.json()["cache"]["status"] == "cache"
    assert refreshed.json()["cache"]["status"] == "network"
    assert gateway.candle_calls == 2


def test_analysis_accepts_camel_case_nested_public_configuration() -> None:
    response = _client().post(
        "/api/v1/analysis",
        json=_analysis_payload(
            indicatorConfig={
                "macd": {"difColor": "#FFFFFF"},
                "kdj": {"kSmoothing": 4, "dSmoothing": 2},
                "boll": {"standardDeviations": 1.5},
                "volumeMa20": {"enabled": False},
            },
            scoreWeights={
                "trend": 1,
                "momentum": 0,
                "volumePrice": 1,
                "position": 0,
                "risk": 0,
            },
        ),
    )

    assert response.status_code == 200
    assert response.json()["score"]["effectiveWeights"] == {
        "trend": 50.0,
        "momentum": 0.0,
        "volumePrice": 50.0,
        "position": 0.0,
        "risk": 0.0,
    }


def test_stale_candle_fallback_is_visible_in_cache_state_and_warnings() -> None:
    gateway = ApiGateway()
    database = Database("sqlite+pysqlite:///:memory:")
    database.create_schema()
    clock = [datetime(2026, 7, 30, 10, tzinfo=UTC)]
    client = TestClient(
        create_app(
            database=database,
            market_gateway=gateway,
            now_provider=lambda: clock[0],
        )
    )
    first = client.post("/api/v1/analysis", json=_analysis_payload())
    gateway._candle_failure = True
    clock[0] += timedelta(days=1)

    stale = client.post("/api/v1/analysis", json=_analysis_payload())

    assert first.status_code == 200
    assert stale.status_code == 200
    assert stale.json()["cache"] == {
        "status": "stale",
        "updatedAt": "2026-07-30",
    }
    assert stale.json()["warnings"] == [
        {
            "code": "DATA_UNAVAILABLE",
            "message": "行情刷新失败，当前使用最近一次缓存数据。",
        }
    ]


def test_short_history_is_a_null_safe_analysis_with_a_structured_warning() -> None:
    response = _client(ApiGateway(candle_count=20)).post(
        "/api/v1/analysis",
        json=_analysis_payload(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["score"]["available"] is False
    assert body["score"]["reason"] == "insufficient_history:80"
    assert body["score"]["totalScore"] is None
    assert body["score"]["grade"] is None
    assert all(
        component["score"] is None for component in body["score"]["breakdown"].values()
    )
    assert body["warnings"] == [
        {
            "code": "INSUFFICIENT_HISTORY",
            "message": "有效交易日不足 80 日，评分暂不可用。",
        }
    ]
    assert "NaN" not in response.text
    _assert_json_contains_only_finite_numbers(body)


def test_unknown_symbol_uses_uniform_not_found_error_envelope() -> None:
    response = _client().post(
        "/api/v1/analysis",
        json=_analysis_payload(symbol="000999"),
    )

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "SYMBOL_NOT_FOUND",
            "message": "未找到股票代码 000999。",
            "retryable": False,
            "details": None,
        }
    }


def test_market_failure_uses_retryable_data_unavailable_error_envelope() -> None:
    response = _client(ApiGateway(candle_failure=True)).post(
        "/api/v1/analysis",
        json=_analysis_payload(),
    )

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "DATA_UNAVAILABLE",
            "message": "行情数据暂时不可用，请稍后重试。",
            "retryable": True,
            "details": None,
        }
    }


@pytest.mark.parametrize(
    "payload",
    [
        _analysis_payload(symbol="1"),
        _analysis_payload(symbol="ABC001"),
        _analysis_payload(range="2y"),
        _analysis_payload(indicatorConfig={"ma": {"periods": [20, 20]}}),
        _analysis_payload(indicatorConfig={"macd": {"fast": 26, "slow": 12}}),
        _analysis_payload(scoreWeights={"trend": -1}),
        _analysis_payload(
            scoreWeights={
                "trend": 0,
                "momentum": 0,
                "volume_price": 0,
                "position": 0,
                "risk": 0,
            }
        ),
    ],
)
def test_invalid_analysis_inputs_use_uniform_invalid_config_error(
    payload: dict[str, object],
) -> None:
    response = _client().post("/api/v1/analysis", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "INVALID_CONFIG"
    assert body["error"]["message"] == "请求参数或分析配置无效。"
    assert body["error"]["retryable"] is False
    assert isinstance(body["error"]["details"], list)


def test_non_finite_weight_is_rejected_without_echoing_nan() -> None:
    response = _client().post(
        "/api/v1/analysis",
        content=(
            '{"symbol":"000001","range":"all","forceRefresh":false,'
            '"indicatorConfig":{},"scoreWeights":{"trend":NaN}}'
        ),
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_CONFIG"
    assert "NaN" not in response.text


def test_non_finite_total_score_uses_standard_data_unavailable_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def nonfinite_score(
        bars: Sequence[MarketBar],
        indicators: IndicatorBundle,
        weights: ScoreWeights | None = None,
    ) -> TechnicalAnalysis:
        result = score_technical_analysis(bars, indicators, weights)
        return replace(result, total_score=cast(int, math.nan))

    monkeypatch.setattr(main_module, "score_technical_analysis", nonfinite_score)
    response = _client(raise_server_exceptions=False).post(
        "/api/v1/analysis",
        json=_analysis_payload(),
    )

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "DATA_UNAVAILABLE",
            "message": "行情数据暂时不可用，请稍后重试。",
            "retryable": True,
            "details": None,
        }
    }
    assert "NaN" not in response.text
    assert "Infinity" not in response.text


@pytest.mark.parametrize(
    ("params", "field"),
    [
        ({"q": "   ", "limit": 5}, "q"),
        ({"q": "银行", "limit": 0}, "limit"),
        ({"q": "银行", "limit": 21}, "limit"),
    ],
)
def test_invalid_search_inputs_use_the_same_error_envelope(
    params: dict[str, str | int],
    field: str,
) -> None:
    response = _client().get("/api/v1/stocks/search", params=params)

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "INVALID_CONFIG"
    assert any(
        field in ".".join(map(str, item["location"]))
        for item in body["error"]["details"]
    )


def test_scan_contract_rejects_duplicate_or_more_than_twenty_symbols() -> None:
    try:
        from app.api_models import ScanRequest
    except ModuleNotFoundError:
        pytest.fail("Task 4 scan request contract has not been implemented")

    valid = ScanRequest.model_validate(
        {
            "symbols": ["000001", "600000"],
            "indicatorConfig": {},
            "scoreWeights": {},
            "forceRefresh": False,
        }
    )

    assert valid.model_dump(mode="json", by_alias=True)["symbols"] == [
        "000001",
        "600000",
    ]
    with pytest.raises(ValidationError, match="unique"):
        ScanRequest.model_validate({"symbols": ["000001", "000001"]})
    with pytest.raises(ValidationError):
        ScanRequest.model_validate({"symbols": [f"{index:06d}" for index in range(21)]})


def test_scan_status_contract_is_persistence_compatible_and_date_safe() -> None:
    try:
        from app.api_models import ScanError, ScanStatusResponse
    except ModuleNotFoundError:
        pytest.fail("Task 4 scan status contracts have not been implemented")

    contract = ScanStatusResponse.model_validate(
        {
            "scanId": "scan-1",
            "status": "running",
            "completedCount": 1,
            "totalCount": 2,
            "marketDate": "2026-07-30",
            "results": [],
            "errors": [
                ScanError(
                    symbol="600000",
                    code="DATA_UNAVAILABLE",
                    message="行情数据暂时不可用。",
                )
            ],
        }
    )

    payload = contract.model_dump(mode="json", by_alias=True)
    assert payload["marketDate"] == "2026-07-30"
    assert payload["errors"][0]["code"] == "DATA_UNAVAILABLE"
    assert "NaN" not in json.dumps(payload, ensure_ascii=False, allow_nan=False)


def test_scan_routes_accept_work_and_expose_status_and_latest() -> None:
    client = _client()

    accepted = client.post(
        "/api/v1/scans",
        json={"symbols": ["000001"], "indicatorConfig": {}, "scoreWeights": {}},
    )

    assert accepted.status_code == 202
    scan_id = accepted.json()["scanId"]
    status_response = client.get(f"/api/v1/scans/{scan_id}")
    latest = client.get("/api/v1/scans/latest")
    assert status_response.status_code == 200
    assert status_response.json()["scanId"] == scan_id
    assert latest.status_code == 200
    assert latest.json()["scanId"] == scan_id


def test_unknown_scan_uses_uniform_not_found_error() -> None:
    response = _client().get("/api/v1/scans/not-a-scan")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SCAN_NOT_FOUND"
