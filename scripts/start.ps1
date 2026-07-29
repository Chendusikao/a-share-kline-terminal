[CmdletBinding()]
param(
    [switch]$NoBrowser,
    [string]$HealthUrl = "http://127.0.0.1:8000/api/v1/health",
    [ValidateRange(1, 300)]
    [int]$ReadinessTimeoutSeconds = 30
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonExecutable = Join-Path $projectRoot ".venv\Scripts\python.exe"
$backendDirectory = Join-Path $projectRoot "backend"
$frontendIndex = Join-Path $projectRoot "frontend\dist\index.html"
$applicationUrl = "http://127.0.0.1:8000"

if (-not (Test-Path -LiteralPath $pythonExecutable)) {
    throw "The Python virtual environment is missing. Run scripts\setup.ps1 first."
}

if (-not (Test-Path -LiteralPath $frontendIndex)) {
    throw "The frontend build is missing. Run scripts\setup.ps1 first."
}

# Network access is opt-in inside the Python gateway. The normal interactive
# launcher makes that intent explicit, while a caller-provided 0 remains
# authoritative for offline and CI runs.
if (-not (Test-Path Env:A_SHARE_ALLOW_AKSHARE_NETWORK)) {
    $env:A_SHARE_ALLOW_AKSHARE_NETWORK = "1"
}

$serviceProcess = $null
$locationPushed = $false
try {
    Write-Host "Starting the A-share K-line terminal at $applicationUrl"
    Push-Location $backendDirectory
    $locationPushed = $true
    $serviceProcess = Start-Process `
        -FilePath $pythonExecutable `
        -ArgumentList @(
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000"
        ) `
        -PassThru `
        -NoNewWindow
    Pop-Location
    $locationPushed = $false

    $deadline = [DateTime]::UtcNow.AddSeconds($ReadinessTimeoutSeconds)
    $ready = $false
    while ([DateTime]::UtcNow -lt $deadline) {
        if ($serviceProcess.HasExited) {
            throw "The FastAPI service exited before it became ready."
        }
        try {
            $response = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 1
            if ($response.status -eq "ok") {
                $ready = $true
                break
            }
        }
        catch {
            Start-Sleep -Milliseconds 250
        }
    }

    if (-not $ready) {
        throw "The service did not become ready within $ReadinessTimeoutSeconds seconds."
    }

    if (-not $NoBrowser) {
        Start-Process $applicationUrl
    }
    Write-Host "Service ready. Press Ctrl+C to stop."
    $serviceProcess.WaitForExit()
    if ($serviceProcess.ExitCode -ne 0) {
        throw "The FastAPI service exited unexpectedly."
    }
}
finally {
    if ($locationPushed) {
        Pop-Location
    }
    if ($null -ne $serviceProcess -and -not $serviceProcess.HasExited) {
        Stop-Process -Id $serviceProcess.Id -Force -ErrorAction SilentlyContinue
        $serviceProcess.WaitForExit()
    }
}
