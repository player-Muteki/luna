# Co-Thinker Windows PowerShell
#  GitHub  .whl 
#  co-thinker 
#
# :
#   powershell -ExecutionPolicy Bypass -File install.ps1
#   powershell -ExecutionPolicy Bypass -File install.ps1 co_thinker-0.0.5-py3-none-any.whl
# :
#   powershell -ExecutionPolicy Bypass -c "curl.exe -sSL https://.../install.ps1 | iex"

$WheelPath = if ($args) { $args[0] } else { "" }

function Write-Step($msg) { Write-Host "`n>>> $msg" -ForegroundColor Cyan }
function Write-Info($msg)  { Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Error($msg){ Write-Host "[ERROR] $msg" -ForegroundColor Red }

Write-Host ""
Write-Host "  ____          _   _   _           _"
Write-Host " / ___|___   __| | | |_| |__  _ __ | | _____ _ __"
Write-Host "| |   / _ \ / _` | | __| '_ \| '_ \| |/ / _ \ '__|"
Write-Host "| |__| (_) | (_| | | |_| | | | | |   <  __/ |"
Write-Host " \____\___/ \__,_|  \__|_| |_|_| |_|_|\_\___|_|"
Write-Host ""
Write-Host "  Co-Thinker v0.0.5 - Windows "

#   .whl  
if ($WheelPath -and (Test-Path $WheelPath)) {
    $WheelFile = Resolve-Path $WheelPath
    Write-Info ": $WheelFile"
} else {
    Write-Step " GitHub "
    $Repo = "player-Muteki/co-thinker"
    Write-Info ": $Repo"

    $ApiUrl = "https://api.github.com/repos/$Repo/releases/latest"
    try {
        $ReleaseData = Invoke-RestMethod -Uri $ApiUrl -Headers @{ "Accept" = "application/json" }
    } catch {
        Write-Error " Release : $_"
        exit 1
    }

    $Asset = $ReleaseData.assets | Where-Object { $_.name -like "*.whl" } | Select-Object -First 1
    if (-not $Asset) {
        Write-Error " .whl "
        exit 1
    }

    $WheelUrl = $Asset.browser_download_url
    $WheelName = Split-Path $WheelUrl -Leaf
    $WheelFile = Join-Path $env:TEMP $WheelName
    Write-Info ": $WheelName"

    try {
        Invoke-WebRequest -Uri $WheelUrl -OutFile $WheelFile -UseBasicParsing
    } catch {
        Write-Error ": $_"
        exit 1
    }
    Write-Info ""
}

#  1.  Python 
Write-Step " Python"
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
    Write-Error " Python >= 3.10"
    exit 1
}

#  2.  
Write-Step " Co-Thinker"

$VenDir = Join-Path $env:USERPROFILE ".co-thinker"
if (Test-Path $VenDir) {
    Write-Warn " $VenDir"
    Remove-Item -Recurse -Force $VenDir
}

& $Python -m venv $VenDir | Out-Null
$Pip = Join-Path $VenDir "Scripts\pip.exe"
& $Pip install $WheelFile --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Error ""
    exit 1
}
Write-Info " $VenDir"

#  3.  PATH  
Write-Step ""

$BinDir = Join-Path $env:USERPROFILE ".local\bin"
if (-not (Test-Path $BinDir)) {
    New-Item -ItemType Directory -Path $BinDir -Force | Out-Null
}

$BatPath = Join-Path $BinDir "co-thinker.cmd"
$CoThinkerExe = Join-Path $VenDir "Scripts\co-thinker.exe"
$batContent = "@echo off`r`n`"$CoThinkerExe`" %*"
$batContent | Set-Content -Path $BatPath
Write-Info ": $BatPath"

#  4.  PATH 
Write-Step " PATH"
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($UserPath -notlike "*$BinDir*") {
    Write-Warn "$BinDir  PATH "
    Write-Host ""
    Write-Host "   PATH..."
    $newPath = $UserPath + ";" + $BinDir
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    Write-Info " co-thinker "
} else {
    Write-Info "PATH  $BinDir"
}

#   
Write-Step ""
Write-Host ""
Write-Host "  "
Write-Host ""
Write-Host "    mkdir my-kb && cd my-kb"
Write-Host "    co-thinker init       #  .env "
Write-Host "    co-thinker start      #  Web "
Write-Host ""
