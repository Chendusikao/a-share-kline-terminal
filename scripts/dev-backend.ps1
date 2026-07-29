[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonExecutable = Join-Path $projectRoot ".venv\Scripts\python.exe"
$backendDirectory = Join-Path $projectRoot "backend"

if (-not (Test-Path -LiteralPath $pythonExecutable)) {
    throw "The Python virtual environment is missing. Run scripts\setup.ps1 first."
}

Push-Location $backendDirectory
try {
    & $pythonExecutable -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
}
finally {
    Pop-Location
}
