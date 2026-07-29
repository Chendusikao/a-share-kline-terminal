from __future__ import annotations

import threading
import time
from datetime import UTC, date, datetime, timedelta

from app.api_models import ScanRequest
from app.persistence import Database


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
    request = ScanRequest(symbols=["000001"])
    first = service.start(request, market_date=date(2026, 7, 30))
    _wait_for_terminal(service, first)
    duplicate = service.start(request, market_date=date(2026, 7, 30))
    forced = service.start(
        request.model_copy(update={"force_refresh": True}),
        market_date=date(2026, 7, 30),
    )
    _wait_for_terminal(service, forced)
    service.shutdown()

    assert duplicate == first
    assert forced != first


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
