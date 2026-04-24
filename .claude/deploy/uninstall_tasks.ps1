#Requires -Version 5.1
<#
.SYNOPSIS
    Removes all Second Brain scheduled tasks from Windows Task Scheduler.
.DESCRIPTION
    Deletes the 5 registered Second Brain tasks. Must be run as Administrator.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# --- Admin check ---
$currentPrincipal = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Warning "This script must be run as Administrator."
    Write-Warning "Right-click PowerShell -> 'Run as administrator', then re-run this script."
    exit 1
}

# --- Task names to remove ---
$taskNames = @(
    'SecondBrain - Heartbeat'
    'SecondBrain - Daily Reflection'
    'SecondBrain - Weekly Compact'
    'SecondBrain - Weekly Prune'
    'SecondBrain - Monthly Rollup'
)

$passCount = 0
$failCount = 0

Write-Host ""
Write-Host "=== Second Brain Task Uninstaller ===" -ForegroundColor Cyan
Write-Host ""

foreach ($taskName in $taskNames) {
    try {
        $output = & schtasks /delete /tn $taskName /f 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  [OK]   Removed: $taskName" -ForegroundColor Green
            $passCount++
        } else {
            # schtasks returns non-zero if task does not exist — treat as warning
            $msg = "$output".Trim()
            if ($msg -match 'cannot find the file|does not exist|ERROR: The system cannot') {
                Write-Host "  [SKIP] Not found: $taskName" -ForegroundColor DarkYellow
            } else {
                Write-Host "  [FAIL] $taskName" -ForegroundColor Red
                Write-Host "         $msg"
                $failCount++
            }
        }
    } catch {
        Write-Host "  [FAIL] $taskName" -ForegroundColor Red
        Write-Host "         $_"
        $failCount++
    }
}

Write-Host ""
Write-Host "Results: $passCount removed, $failCount failed." -ForegroundColor Cyan

if ($failCount -eq 0) {
    Write-Host "All Second Brain tasks have been removed." -ForegroundColor Green
} else {
    Write-Host "Some tasks could not be removed. Review errors above." -ForegroundColor Yellow
}
Write-Host ""
