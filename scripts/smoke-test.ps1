#Requires -Version 5.1
<#
.SYNOPSIS
    Basic smoke test against a running MT5 Execution Bridge instance.
.DESCRIPTION
    Calls /health and /api/status, then submits one signal from
    examples/buy-signal.json and reports its resulting status.
    Assumes the service is already running (see run-dev.ps1).
#>

param(
    [string]$BaseUrl = "http://127.0.0.1:8200"
)

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

Write-Host "GET /health"
$health = Invoke-RestMethod -Uri "$BaseUrl/health"
$health | ConvertTo-Json

Write-Host "`nGET /api/status"
$status = Invoke-RestMethod -Uri "$BaseUrl/api/status"
$status | ConvertTo-Json

Write-Host "`nPOST /api/signals (examples/buy-signal.json)"
$signal = Get-Content "examples/buy-signal.json" -Raw | ConvertFrom-Json
$signal.signal_id = "smoke-test-$(Get-Date -Format 'yyyyMMddTHHmmss')"
$signal.timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$body = $signal | ConvertTo-Json

$submitted = Invoke-RestMethod -Uri "$BaseUrl/api/signals" -Method Post -Body $body -ContentType "application/json"
$submitted | ConvertTo-Json

Start-Sleep -Seconds 2

Write-Host "`nGET /api/signals/$($signal.signal_id)"
$result = Invoke-RestMethod -Uri "$BaseUrl/api/signals/$($signal.signal_id)"
$result | ConvertTo-Json
