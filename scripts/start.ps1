[CmdletBinding()]
param(
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonExecutable = Join-Path $projectRoot ".venv\Scripts\python.exe"
$backendDirectory = Join-Path $projectRoot "backend"
$frontendIndex = Join-Path $projectRoot "frontend\dist\index.html"
$applicationUrl = "http://127.0.0.1:8000"
$healthUrl = "$applicationUrl/api/v1/health"

if (-not (Test-Path -LiteralPath $pythonExecutable)) {
    throw "The Python virtual environment is missing. Run scripts\setup.ps1 first."
}

if (-not (Test-Path -LiteralPath $frontendIndex)) {
    throw "The frontend build is missing. Run scripts\setup.ps1 first."
}

$browserJob = Start-Job -ScriptBlock {
    param($HealthUrl, $ApplicationUrl, $SkipBrowser)

    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        try {
            $response = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 1
            if ($response.status -eq "ok") {
                if (-not $SkipBrowser) {
                    Start-Process $ApplicationUrl
                }
                return
            }
        }
        catch {
            Start-Sleep -Milliseconds 500
        }
    }

    throw "The service did not become ready within 30 seconds."
} -ArgumentList $healthUrl, $applicationUrl, $NoBrowser.IsPresent

try {
    Write-Host "Starting the A-share K-line terminal at $applicationUrl"
    Write-Host "Press Ctrl+C to stop the service."
    Push-Location $backendDirectory
    & $pythonExecutable -m uvicorn app.main:app --host 127.0.0.1 --port 8000
    if ($LASTEXITCODE -ne 0) {
        throw "The FastAPI service exited unexpectedly."
    }
}
finally {
    Pop-Location
    Stop-Job -Job $browserJob -ErrorAction SilentlyContinue
    Remove-Job -Job $browserJob -Force -ErrorAction SilentlyContinue
}
