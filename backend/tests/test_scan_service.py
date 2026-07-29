from __future__ import annotations

import threading
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pandas as pd

from app.api_models import ScanRequest
from app.market_service import CandleService
from app.persistence import CandleRepository, Database, ScanCandleRepository


def _wait_for_terminal(service: object, scan_id: str) -> object:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        status = service.get_status(scan_id)  # type: ignore[attr-defined]
        if status is not None and status.status in {"completed", "failed"}:
            return status
        time.sleep(0.01)
    raise AssertionError("scan did not finish")


def test_scan_retries_each_failed_symbol_twice_and_limits_workers_to_three() -> None:
    from app.scan_service import ScanOutcome, ScanService

    database = Database("sqlite+pysqlite:///:memory:")
    database.create_schema()
    lock = threading.Lock()
    calls: dict[str, int] = {}
    active = 0
    peak = 0

    def analyze(symbol: str, _request: ScanRequest) -> ScanOutcome:
        nonlocal active, peak
        with lock:
            calls[symbol] = calls.get(symbol, 0) + 1
            active += 1
            peak = max(peak, active)
        time.sleep(0.02)
        with lock:
            active -= 1
        if symbol == "000002":
            raise RuntimeError("upstream timeout")
        return ScanOutcome(
            score=60,
            grade="偏强",
            breakdown={},
            insights=[],
            data_status="network",
            error_code=None,
        )

    service = ScanService(database, analyze_symbol=analyze)
    request = ScanRequest(
        symbols=["000001", "000002", "000003", "000004", "000005"]
    )
    scan_id = service.start(request, market_date=date(2026, 7, 30))
    result = _wait_for_terminal(service, scan_id)
    service.shutdown()

    assert result.status == "completed"  # type: ignore[attr-defined]
    assert result.completed_count == 5  # type: ignore[attr-defined]
    assert [item.symbol for item in result.results] == [  # type: ignore[attr-defined]
        "000001",
        "000003",
        "000004",
        "000005",
    ]
    assert result.errors[0].symbol == "000002"  # type: ignore[attr-defined]
    assert result.errors[0].message == "upstream timeout"  # type: ignore[attr-defined]
    assert calls["000002"] == 3
    assert all(count == 1 for symbol, count in calls.items() if symbol != "000002")
    assert peak == 3


def test_same_market_date_request_is_deduplicated_unless_forced() -> None:
    from app.scan_service import ScanOutcome, ScanService

    database = Database("sqlite+pysqlite:///:memory:")
    database.create_schema()

    def analyze(symbol: str, _request: ScanRequest) -> ScanOutcome:
        return ScanOutcome(50, "中性", {}, [], "cache", None)

    service = ScanService(database, analyze_symbol=analyze)
    request = ScanRequest(symbols=["000001", "600000"])
    first = service.start(request, market_date=date(2026, 7, 30))
    _wait_for_terminal(service, first)
    duplicate = service.start(
        request.model_copy(update={"symbols": ["600000", "000001"]}),
        market_date=date(2026, 7, 30),
    )
    forced = service.start(
        request.model_copy(update={"force_refresh": True}),
        market_date=date(2026, 7, 30),
    )
    _wait_for_terminal(service, forced)
    service.shutdown()

    assert duplicate == first
    assert forced != first


class BoundedHistoryGateway:
    def __init__(self) -> None:
        self.requested_window: tuple[date | None, date | None] | None = None
        self.candle_calls = 0

    def fetch_stock_list(self) -> pd.DataFrame:
        raise AssertionError("stock catalog fetch is not expected")

    def fetch_daily_candles(
        self,
        symbol: str,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        self.candle_calls += 1
        self.requested_window = (start_date, end_date)
        first_day = date(2024, 1, 1)
        rows = []
        for index in range(600):
            close = 10 + index * 0.01
            rows.append(
                {
                    "日期": (first_day + timedelta(days=index)).isoformat(),
                    "开盘": close - 0.05,
                    "最高": close + 0.1,
                    "最低": close - 0.1,
                    "收盘": close,
                    "成交量": 1_000 + index,
                    "成交额": close * (1_000 + index),
                }
            )
        return pd.DataFrame(rows)


def test_real_scan_requests_and_persists_only_derived_score_history(
    tmp_path: Path,
) -> None:
    from app.scan_service import ScanService, required_scan_history

    database = Database(tmp_path / "scan.sqlite3")
    database.create_schema()
    gateway = BoundedHistoryGateway()
    now = datetime(2026, 7, 30, 16, tzinfo=UTC)
    request = ScanRequest.model_validate(
        {
            "symbols": ["000001"],
            "indicatorConfig": {
                "macd": {"fast": 12, "slow": 120, "signal": 50},
                "atr": {"period": 100},
            },
        }
    )
    service = ScanService(
        database,
        CandleService(database, gateway),
        now_provider=lambda: now,
    )

    scan_id = service.start(request, market_date=date(2026, 7, 30))
    result = _wait_for_terminal(service, scan_id)
    service.shutdown()

    assert result.status == "completed"  # type: ignore[attr-defined]
    assert result.results[0].score is not None  # type: ignore[attr-defined]
    assert required_scan_history(request) == 170
    assert gateway.requested_window is not None
    start_date, end_date = gateway.requested_window
    assert start_date is not None
    assert end_date == now.date()
    assert start_date < end_date
    with database.session() as session:
        detail_cache = CandleRepository(session).list_symbol("000001")
        scan_cache = ScanCandleRepository(session).list_symbol("000001")
    assert detail_cache == []
    assert len(scan_cache) == 170


def test_fresh_full_detail_cache_populates_bounded_scan_cache_without_truncation(
    tmp_path: Path,
) -> None:
    from app.scan_service import ScanService

    database = Database(tmp_path / "fresh-cache.sqlite3")
    database.create_schema()
    gateway = BoundedHistoryGateway()
    now = datetime(2026, 7, 30, 16, tzinfo=UTC)
    candle_service = CandleService(database, gateway)
    detail = candle_service.get("000001", now=now, range_name="all")
    assert len(detail.candles) == 600

    service = ScanService(
        database,
        candle_service,
        now_provider=lambda: now,
    )
    scan_id = service.start(
        ScanRequest(symbols=["000001"]),
        market_date=date(2026, 7, 30),
    )
    result = _wait_for_terminal(service, scan_id)
    service.shutdown()

    assert result.results[0].score is not None  # type: ignore[attr-defined]
    with database.session() as session:
        detail_cache = CandleRepository(session).list_symbol("000001")
        scan_cache = ScanCandleRepository(session).list_symbol("000001")
    assert len(detail_cache) == 600
    assert len(scan_cache) == 80
    detail_again = candle_service.get("000001", now=now, range_name="all")
    assert len(detail_again.candles) == 600
    assert gateway.candle_calls == 1


def test_startup_recovery_marks_incomplete_runs_failed_and_retains_latest_thirty() -> (
    None
):
    from app.persistence import ScanRepository

    database = Database("sqlite+pysqlite:///:memory:")
    database.create_schema()
    started = datetime(2026, 6, 1, tzinfo=UTC)
    with database.session() as session:
        repository = ScanRepository(session)
        for index in range(31):
            repository.create_run(
                scan_id=f"scan-{index:02d}",
                market_date=date(2026, 6, 1) + timedelta(days=index),
                config_hash=f"hash-{index}",
                symbols=["000001"],
                created_at=started + timedelta(days=index),
            )
            if index > 0:
                repository.finish_run(
                    f"scan-{index:02d}",
                    completed_at=started + timedelta(days=index, minutes=1),
                )
        recovered = repository.recover_incomplete(
            completed_at=datetime(2026, 7, 30, tzinfo=UTC)
        )
        repository.retain_latest(30)
        session.commit()

    with database.session() as session:
        repository = ScanRepository(session)
        assert recovered == 1
        assert repository.get_run("scan-00") is None
        assert len(repository.list_runs()) == 30


def test_scan_status_reports_change_from_previous_completed_batch() -> None:
    from app.scan_service import ScanOutcome, ScanService

    database = Database("sqlite+pysqlite:///:memory:")
    database.create_schema()
    scores = iter([52, 61])

    def analyze(symbol: str, _request: ScanRequest) -> ScanOutcome:
        return ScanOutcome(next(scores), "偏强", {}, [], "network", None)

    service = ScanService(database, analyze_symbol=analyze)
    request = ScanRequest(symbols=["000001"])
    first = service.start(request, market_date=date(2026, 7, 29))
    _wait_for_terminal(service, first)
    second = service.start(request, market_date=date(2026, 7, 30))
    result = _wait_for_terminal(service, second)
    service.shutdown()

    assert result.results[0].score_change == 9  # type: ignore[attr-defined]
