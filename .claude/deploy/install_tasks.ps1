#Requires -Version 5.1
<#
.SYNOPSIS
    Registers all Second Brain scheduled tasks with Windows Task Scheduler.
.DESCRIPTION
    Reads XML task definitions from the tasks\ subdirectory and registers each
    via schtasks. Must be run as Administrator.
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

# --- Task definitions (xml path -> task name) ---
# Most XMLs live in deploy/tasks/; the claude-mem bridge lives in .claude/tasks/.
$projectRoot = 'C:\Users\cliao\Desktop\2nd_Brain'
$deployTasksDir = Join-Path $PSScriptRoot 'tasks'
$extraTasksDir  = Join-Path $projectRoot '.claude\tasks'

$tasks = [ordered]@{
    (Join-Path $deployTasksDir 'heartbeat.xml')                           = 'SecondBrain - Heartbeat'
    (Join-Path $deployTasksDir 'reflect.xml')                             = 'SecondBrain - Daily Reflection'
    (Join-Path $deployTasksDir 'auto_approve.xml')                        = 'SecondBrain - AutoApprove'
    (Join-Path $deployTasksDir 'compact_weekly.xml')                      = 'SecondBrain - Weekly Compact'
    (Join-Path $deployTasksDir 'prune_weekly.xml')                        = 'SecondBrain - Weekly Prune'
    (Join-Path $deployTasksDir 'monthly_rollup.xml')                      = 'SecondBrain - Monthly Rollup'
    (Join-Path $extraTasksDir  'SecondBrain-ClaudeMemBridge.xml')         = 'SecondBrain - ClaudeMemBridge'
}
$passCount = 0
$failCount = 0

Write-Host ""
Write-Host "=== Second Brain Task Installer ===" -ForegroundColor Cyan
Write-Host "Deploy tasks:  $deployTasksDir"
Write-Host "Extra tasks:   $extraTasksDir"
Write-Host ""

foreach ($xmlPath in $tasks.Keys) {
    $taskName = $tasks[$xmlPath]

    if (-not (Test-Path $xmlPath)) {
        Write-Host "  [FAIL] $taskName" -ForegroundColor Red
        Write-Host "         XML not found: $xmlPath"
        $failCount++
        continue
    }

    try {
        $output = & schtasks /create /xml $xmlPath /tn $taskName /f 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  [OK]   $taskName" -ForegroundColor Green
            $passCount++
        } else {
            Write-Host "  [FAIL] $taskName" -ForegroundColor Red
            Write-Host "         $output"
            $failCount++
        }
    } catch {
        Write-Host "  [FAIL] $taskName" -ForegroundColor Red
        Write-Host "         $_"
        $failCount++
    }
}

Write-Host ""
Write-Host "Results: $passCount installed, $failCount failed." -ForegroundColor Cyan

if ($failCount -eq 0) {
    Write-Host "All tasks installed. Run them from Task Scheduler or trigger manually." -ForegroundColor Green
} else {
    Write-Host "Some tasks failed to install. Review errors above." -ForegroundColor Yellow
}
Write-Host ""
