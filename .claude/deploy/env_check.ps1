#Requires -Version 5.1
<#
.SYNOPSIS
    Verifies all prerequisites for the Second Brain scheduled tasks.
.DESCRIPTION
    Checks Python venv, packages, .env keys, Node.js, optional tools, vault
    files, and OAuth tokens. Prints PASS/WARN/FAIL for each item and a final
    summary.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'SilentlyContinue'

$projectRoot = 'C:\Users\cliao\Desktop\2nd_Brain'
$venvPython  = Join-Path $projectRoot '.claude\venv\Scripts\python.exe'

$passCount     = 0
$failCount     = 0
$warnCount     = 0
$failedItems   = [System.Collections.Generic.List[string]]::new()
$fixNeeded     = [System.Collections.Generic.List[string]]::new()

function Write-Pass {
    param([string]$Label)
    Write-Host "  [PASS] $Label" -ForegroundColor Green
    $script:passCount++
}

function Write-Fail {
    param([string]$Label, [string]$Detail = '')
    Write-Host "  [FAIL] $Label" -ForegroundColor Red
    if ($Detail) { Write-Host "         $Detail" -ForegroundColor DarkRed }
    $script:failCount++
    $script:failedItems.Add($Label) | Out-Null
    $script:fixNeeded.Add($Label) | Out-Null
}

function Write-Warn {
    param([string]$Label, [string]$Detail = '')
    Write-Host "  [WARN] $Label" -ForegroundColor Yellow
    if ($Detail) { Write-Host "         $Detail" -ForegroundColor DarkYellow }
    $script:warnCount++
}

Write-Host ""
Write-Host "=== Second Brain Environment Check ===" -ForegroundColor Cyan
Write-Host ""

# -----------------------------------------------------------------------
# 1. Python venv exists
# -----------------------------------------------------------------------
Write-Host "-- Python --"
if (Test-Path $venvPython) {
    Write-Pass "Python venv exists: $venvPython"
} else {
    Write-Fail "Python venv exists" "Not found: $venvPython"
}

# -----------------------------------------------------------------------
# 2. Python version >= 3.9
# -----------------------------------------------------------------------
if (Test-Path $venvPython) {
    $versionOutput = & $venvPython --version 2>&1
    if ($versionOutput -match 'Python (\d+)\.(\d+)') {
        $major = [int]$Matches[1]
        $minor = [int]$Matches[2]
        if ($major -gt 3 -or ($major -eq 3 -and $minor -ge 9)) {
            Write-Pass "Python version >= 3.9 ($versionOutput)"
        } else {
            Write-Fail "Python version >= 3.9" "Found $versionOutput — upgrade required"
        }
    } else {
        Write-Fail "Python version >= 3.9" "Could not parse version from: $versionOutput"
    }
} else {
    Write-Warn "Python version check skipped (venv not found)"
}

# -----------------------------------------------------------------------
# 3. Required Python packages
# -----------------------------------------------------------------------
Write-Host ""
Write-Host "-- Python packages --"
$requiredPackages = @(
    'anthropic'
    'fastembed'
    'google-api-python-client'
    'PyGithub'
    'python-dotenv'
    'win10toast-click'
)

foreach ($pkg in $requiredPackages) {
    if (Test-Path $venvPython) {
        $pipOutput = & $venvPython -m pip show $pkg 2>&1
        if ($LASTEXITCODE -eq 0 -and $pipOutput -match 'Name:') {
            Write-Pass "Package installed: $pkg"
        } else {
            Write-Fail "Package installed: $pkg" "Run: $venvPython -m pip install $pkg"
        }
    } else {
        Write-Warn "Package check skipped: $pkg (venv not found)"
    }
}

# -----------------------------------------------------------------------
# 4. .env file and required keys
# -----------------------------------------------------------------------
Write-Host ""
Write-Host "-- Environment file --"
$envFile = Join-Path $projectRoot '.env'
$requiredKeys = @(
    'GMAIL_CLIENT_ID'
    'GMAIL_CLIENT_SECRET'
    'GITHUB_TOKEN'
    'ANTHROPIC_API_KEY'
)

if (Test-Path $envFile) {
    Write-Pass ".env file exists: $envFile"
    $envContent = Get-Content $envFile -Raw

    foreach ($key in $requiredKeys) {
        # Match KEY=<non-empty-value> (ignore commented lines)
        if ($envContent -match "(?m)^$key\s*=\s*.+") {
            Write-Pass ".env key present: $key"
        } else {
            Write-Fail ".env key present: $key" "Add $key=<value> to $envFile"
        }
    }
} else {
    Write-Fail ".env file exists" "Create $envFile with required keys"
    foreach ($key in $requiredKeys) {
        Write-Fail ".env key present: $key" "(no .env file)"
    }
}

# -----------------------------------------------------------------------
# 5. Node.js
# -----------------------------------------------------------------------
Write-Host ""
Write-Host "-- Node.js --"
$nodeVersion = & node --version 2>&1
if ($LASTEXITCODE -eq 0 -and $nodeVersion -match 'v\d+') {
    Write-Pass "Node.js installed: $nodeVersion"
} else {
    Write-Fail "Node.js installed" "Install from https://nodejs.org"
}

# -----------------------------------------------------------------------
# 6. codeburn (optional)
# -----------------------------------------------------------------------
Write-Host ""
Write-Host "-- Optional tools --"
$codeburnVersion = & codeburn --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Pass "codeburn available: $codeburnVersion"
} else {
    Write-Warn "codeburn not found" "Optional — install via npm if needed"
}

# -----------------------------------------------------------------------
# 7. Vault — SOUL.md
# -----------------------------------------------------------------------
Write-Host ""
Write-Host "-- Vault --"
$soulFile = Join-Path $projectRoot 'vault\SOUL.md'
if (Test-Path $soulFile) {
    Write-Pass "Vault SOUL.md exists: $soulFile"
} else {
    Write-Fail "Vault SOUL.md exists" "Create $soulFile before running tasks"
}

# -----------------------------------------------------------------------
# 8. OAuth token files (warn only — not blocking)
# -----------------------------------------------------------------------
Write-Host ""
Write-Host "-- OAuth tokens (warnings only) --"
$oauthFiles = @{
    'Gmail token'    = Join-Path $projectRoot '.claude\data\secrets\gmail_token.json'
    'GCal token'     = Join-Path $projectRoot '.claude\data\secrets\gcal_token.json'
}

foreach ($label in $oauthFiles.Keys) {
    $path = $oauthFiles[$label]
    if (Test-Path $path) {
        Write-Pass "${label}: $path"
    } else {
        Write-Warn "${label} not found" "Run the OAuth flow to generate: $path"
    }
}

# -----------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------
Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "Summary: $passCount PASS  |  $warnCount WARN  |  $failCount FAIL" -ForegroundColor Cyan
Write-Host ""

if ($failCount -eq 0) {
    Write-Host "Ready to install tasks." -ForegroundColor Green
    Write-Host "Run install_tasks.ps1 as Administrator to register all scheduled tasks."
} else {
    Write-Host "Fix the following before installing tasks:" -ForegroundColor Yellow
    foreach ($item in $fixNeeded) {
        Write-Host "  - $item" -ForegroundColor Red
    }
}

if ($warnCount -gt 0) {
    Write-Host ""
    Write-Host "Warnings are non-blocking but some features may not work until resolved." -ForegroundColor DarkYellow
}
Write-Host ""
