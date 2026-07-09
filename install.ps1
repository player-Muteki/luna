# Co-Thinker install script (Windows PowerShell)
# Downloads the latest .whl from GitHub and installs to a dedicated venv.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File install.ps1
#   powershell -ExecutionPolicy Bypass -File install.ps1 co_thinker-0.0.11-py3-none-any.whl
# Online (no download):
#   powershell -ExecutionPolicy Bypass -c "curl.exe -sSL URL | ..."

$WheelPath = if ($args) { $args[0] } else { "" }

function Write-Step($msg) { Write-Host "`n>>> $msg" -ForegroundColor Cyan }
function Write-Info($msg)  { Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Error($msg){ Write-Host "[ERROR] $msg" -ForegroundColor Red }

Write-Host ""
Write-Host "  ____          _   _   _           _"
Write-Host " / ___|___   __| | | |_| |__  _ __ | | _____ _ __"
Write-Host "| |   / _ \ / _' | | __| '_ \| '_ \| |/ / _ \ '__|"
Write-Host "| |__| (_) | (_| | | |_| | | | | |   <  __/ |"
Write-Host " \____\___/ \__,_|  \__|_| |_|_| |_|_|\_\___|_|"
Write-Host ""
Write-Host "  Co-Thinker v0.0.11 - Windows Installer"

# ── Handle local .whl or auto-download ─────────────────────
if ($WheelPath -and (Test-Path $WheelPath)) {
    $WheelFile = Resolve-Path $WheelPath
    Write-Info "Using local file: $WheelFile"
} else {
    Write-Step "Fetching latest release from GitHub"
    $Repo = "player-Muteki/co-thinker"
    Write-Info "Repo: $Repo"

    $ApiUrl = "https://api.github.com/repos/$Repo/releases/latest"
    try {
        $ReleaseData = Invoke-RestMethod -Uri $ApiUrl -Headers @{ "Accept" = "application/json" }
    } catch {
        Write-Error "Failed to fetch release info: $_"
        exit 1
    }

    $Asset = $ReleaseData.assets | Where-Object { $_.name -like "*.whl" } | Select-Object -First 1
    if (-not $Asset) {
        Write-Error "No .whl file found in latest release"
        exit 1
    }

    $WheelUrl = $Asset.browser_download_url
    $WheelName = Split-Path $WheelUrl -Leaf
    $WheelFile = Join-Path $env:TEMP $WheelName
    Write-Info "Downloading: $WheelName"

    try {
        Invoke-WebRequest -Uri $WheelUrl -OutFile $WheelFile -UseBasicParsing
    } catch {
        Write-Error "Download failed: $_"
        exit 1
    }
    Write-Info "Download complete"
}

# ── 1. Check Python ────────────────────────────────────────
Write-Step "Checking Python"
$Python = $null
foreach ($cmd in @("python3", "python")) {
    try {
        $ver = & $cmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        if ($ver -and [version]$ver -ge [version]"3.10") {
            $Python = $cmd
            Write-Info "Python $(& $cmd --version 2>&1)"
            break
        }
    } catch {}
}
if (-not $Python) {
    Write-Error "Requires Python >= 3.10"
    exit 1
}

# ── 2. Install to dedicated venv ───────────────────────────
Write-Step "Installing Co-Thinker"

$VenDir = Join-Path $env:USERPROFILE ".co-thinker"
if (Test-Path $VenDir) {
    Write-Warn "$VenDir exists, reinstalling"
    Remove-Item -Recurse -Force $VenDir
}

& $Python -m venv $VenDir | Out-Null
$Pip = Join-Path $VenDir "Scripts\pip.exe"
& $Pip install $WheelFile
if ($LASTEXITCODE -ne 0) {
    Write-Error "Installation failed"
    exit 1
}
Write-Info "Installed to $VenDir"

# ── 3. Install web frontend dependencies ─────────────────────
Write-Step "Installing web frontend dependencies"
$WebDir = & $Python -c "import web, os; print(os.path.dirname(web.__file__))" 2>$null
if ($WebDir -and (Test-Path (Join-Path $WebDir "package.json"))) {
    # Check if npm is available
    $NpmPath = Get-Command "npm" -ErrorAction SilentlyContinue
    if ($NpmPath) {
        Write-Info "Installing frontend dependencies (npm install)..."
        Push-Location $WebDir
        & npm install --quiet 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Info "Frontend dependencies installed"
        } else {
            Write-Warn "npm install failed, will retry on first 'co-thinker start'"
        }
        Pop-Location
    } else {
        Write-Warn "npm not found. Install Node.js (https://nodejs.org/) for best experience"
        Write-Warn "First 'co-thinker start' will auto-install dependencies"
    }
} else {
    Write-Info "Web frontend package not detected, skipping frontend setup"
}

# ── 4. Create PATH shortcut ──────────────────────────────
Write-Step "Configuring system PATH"

$BinDir = Join-Path $env:USERPROFILE ".local\bin"
if (-not (Test-Path $BinDir)) {
    New-Item -ItemType Directory -Path $BinDir -Force | Out-Null
}

$BatPath = Join-Path $BinDir "co-thinker.cmd"
$CoThinkerExe = Join-Path $VenDir "Scripts\co-thinker.exe"
"@echo off`r`n`"$CoThinkerExe`" %*" | Set-Content -Path $BatPath
Write-Info "Created shortcut: $BatPath"

# ── 5. Check PATH ──────────────────────────────────────────
Write-Step "Checking PATH"
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($UserPath -notlike "*$BinDir*") {
    Write-Warn "$BinDir not in PATH"
    Write-Host ""
    Write-Host "  Auto-adding to user environment variable PATH..."
    $newPath = $UserPath + ";" + $BinDir
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    Write-Info "Added. Restart your terminal for co-thinker to be available"
} else {
    Write-Info "PATH already contains $BinDir"
}

# ── Done ─────────────────────────────────────────────────────
Write-Step "Installation complete!"
Write-Host ""
Write-Host "  To get started:"
Write-Host ""
Write-Host "    mkdir my-kb; cd my-kb"
Write-Host "    co-thinker init"
Write-Host "    co-thinker start"
Write-Host ""
