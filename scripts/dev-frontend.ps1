[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$frontendDirectory = Join-Path $projectRoot "frontend"

if (-not (Test-Path -LiteralPath (Join-Path $frontendDirectory "node_modules"))) {
    throw "Frontend dependencies are missing. Run scripts\setup.ps1 first."
}

& npm --prefix $frontendDirectory run dev
