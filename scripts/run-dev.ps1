#Requires -Version 5.1
<#
.SYNOPSIS
    Runs the MT5 Execution Bridge locally with uvicorn (development mode).
#>

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

if (-not (Test-Path ".env")) {
    Write-Warning ".env not found. Copying .env.example -> .env (dry-run defaults)."
    Copy-Item ".env.example" ".env"
}

if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..."
    py -3 -m venv .venv
}

& ".venv\Scripts\python.exe" -m pip install -q -e ".[dev]"
& ".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8200 --reload
