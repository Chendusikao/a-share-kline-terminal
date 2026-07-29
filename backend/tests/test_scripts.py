from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.skipif(
    sys.platform != "win32", reason="PowerShell launcher is Windows-only"
)
def test_start_script_returns_failure_when_readiness_never_succeeds() -> None:
    project_root = Path(__file__).parents[2]
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(project_root / "scripts" / "start.ps1"),
            "-NoBrowser",
            "-HealthUrl",
            "http://127.0.0.1:1/api/v1/health",
            "-ReadinessTimeoutSeconds",
            "1",
        ],
        cwd=project_root,
        text=True,
        capture_output=True,
        timeout=15,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode != 0
    assert "did not become ready" in output
