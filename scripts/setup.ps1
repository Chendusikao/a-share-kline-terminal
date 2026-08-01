[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$virtualEnvironment = Join-Path $projectRoot ".venv"
$pythonExecutable = Join-Path $virtualEnvironment "Scripts\python.exe"
$backendLock = Join-Path $projectRoot "backend\requirements.lock"
$frontendDirectory = Join-Path $projectRoot "frontend"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python was not found. Install Python 3.14 first."
}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "npm was not found. Install Node.js 24 first."
}

if (-not (Test-Path -LiteralPath $pythonExecutable)) {
    Write-Host "Creating the Python virtual environment..."
    & python -m venv $virtualEnvironment
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create the Python virtual environment."
    }
}

Write-Host "Installing locked backend dependencies..."
& $pythonExecutable -m pip install --disable-pip-version-check -r $backendLock
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install backend dependencies."
}

Write-Host "Installing locked frontend dependencies..."
& npm --prefix $frontendDirectory ci --no-audit --no-fund
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install frontend dependencies."
}

Write-Host "Building the frontend..."
& npm --prefix $frontendDirectory run build
if ($LASTEXITCODE -ne 0) {
    throw "Failed to build the frontend."
}

Write-Host "Setup complete. Run scripts\start.ps1 to start the application."
