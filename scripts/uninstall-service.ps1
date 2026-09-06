#Requires -Version 5.1
<#
.SYNOPSIS
    Removes the scheduled task created by install-service.ps1.
#>

param(
    [string]$TaskName = "MT5ExecutionBridge"
)

$ErrorActionPreference = "Stop"

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if (-not $existing) {
    Write-Host "No scheduled task named '$TaskName' found."
    exit 0
}

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
Write-Host "Removed scheduled task '$TaskName'."
