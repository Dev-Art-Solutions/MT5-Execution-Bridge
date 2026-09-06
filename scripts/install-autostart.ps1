#Requires -Version 5.1
<#
.SYNOPSIS
    Registers the MT5 Execution Bridge to auto-start at user logon.
.DESCRIPTION
    Uses Windows Task Scheduler rather than a Windows Service. The
    MetaTrader5 Python integration talks to a terminal running in an
    interactive user session; a Windows Service normally runs in Session 0
    with no desktop interaction, which is not guaranteed to work with MT5
    and has not been validated for this project (see docs/INSTALLATION.md).
    Task Scheduler "at logon" runs in the same session as the terminal.
#>

param(
    [string]$TaskName = "MT5ExecutionBridge"
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$pythonExe = Join-Path $repoRoot ".venv\Scripts\pythonw.exe"

if (-not (Test-Path $pythonExe)) {
    throw "Virtual environment not found at $pythonExe. Run scripts\run-dev.ps1 once first."
}

$action = New-ScheduledTaskAction -Execute $pythonExe `
    -Argument "-m uvicorn app.main:app --host 127.0.0.1 --port 8200" `
    -WorkingDirectory $repoRoot

$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null

Write-Host "Registered scheduled task '$TaskName' to start MT5 Execution Bridge at logon."
Write-Host "Verify manually: Start-ScheduledTask -TaskName '$TaskName'"
