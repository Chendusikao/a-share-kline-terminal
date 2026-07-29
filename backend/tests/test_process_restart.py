from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen


def _free_local_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _json_request(
    url: str,
    *,
    method: str = "GET",
    body: dict[str, object] | None = None,
) -> tuple[int, dict[str, Any]]:
    payload = json.dumps(body).encode() if body is not None else None
    request = Request(
        url,
        data=payload,
        method=method,
        headers={"Content-Type": "application/json"} if payload else {},
    )
    with urlopen(request, timeout=2) as response:
        return response.status, json.loads(response.read())


@contextmanager
def _offline_backend(
    *,
    database_path: Path,
    scan_delay_seconds: float,
) -> Iterator[str]:
    port = _free_local_port()
    environment = os.environ.copy()
    environment.update(
        {
            "A_SHARE_ALLOW_AKSHARE_NETWORK": "0",
            "A_SHARE_E2E_DATABASE_PATH": str(database_path),
            "A_SHARE_E2E_SCAN_DELAY_SECONDS": str(scan_delay_seconds),
        }
    )
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "tests.support.offline_server:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=Path(__file__).parents[1],
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base_url = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError("offline backend exited before becoming ready")
        try:
            status, payload = _json_request(f"{base_url}/api/v1/health")
            if status == 200 and payload == {"status": "ok"}:
                break
        except (OSError, URLError):
            time.sleep(0.05)
    else:
        raise AssertionError("offline backend did not become ready")
    try:
        yield base_url
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def test_actual_backend_restart_recovers_persisted_incomplete_scan(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "restart.sqlite3"
    with _offline_backend(
        database_path=database_path,
        scan_delay_seconds=10,
    ) as base_url:
        accepted_status, accepted = _json_request(
            f"{base_url}/api/v1/scans",
            method="POST",
            body={
                "symbols": ["000001"],
                "indicatorConfig": {},
                "scoreWeights": {},
            },
        )
        assert accepted_status == 202
        scan_id = accepted["scanId"]
        status, before_restart = _json_request(f"{base_url}/api/v1/scans/{scan_id}")
        assert status == 200
        assert before_restart["status"] in {"pending", "running"}

    with _offline_backend(
        database_path=database_path,
        scan_delay_seconds=0,
    ) as restarted_url:
        status, recovered = _json_request(f"{restarted_url}/api/v1/scans/{scan_id}")

    assert status == 200
    assert recovered["status"] == "failed"
    assert recovered["completedCount"] == 1
    assert recovered["errors"][0]["code"] == "DATA_UNAVAILABLE"
