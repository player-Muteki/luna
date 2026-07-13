# Luna install script (Windows PowerShell)
# Downloads the latest .whl from GitHub and installs to a dedicated venv.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File install.ps1
#   powershell -ExecutionPolicy Bypass -File install.ps1 luna-0.0.11-py3-none-any.whl
# Online (no download):
#   powershell -ExecutionPolicy Bypass -c "curl.exe -sSL URL | ..."

$WheelPath = if ($args) { $args[0] } else { "" }

function Write-Step($msg) { Write-Host "`n>>> $msg" -ForegroundColor Cyan }
function Write-Info($msg)  { Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Error($msg){ Write-Host "[ERROR] $msg" -ForegroundColor Red }

Write-Host ""
Write-Host " _                    "
Write-Host "| |                   "
Write-Host "| |     ___  _ __ ___ "
Write-Host "| |    / _ \| '__/ _ \"
Write-Host "| |___| (_) | | |  __/"
Write-Host "|______\___/|_|  \___|"
Write-Host ""
Write-Host "  Luna Installer"

# ── Handle local .whl or auto-download ─────────────────────
if ($WheelPath -and (Test-Path $WheelPath)) {
    $WheelFile = Resolve-Path $WheelPath
    Write-Info "Using local file: $WheelFile"
} else {
    Write-Step "Fetching latest release from GitHub"
    $Repo = "player-Muteki/luna"
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

# ── Extract wheel version ────────────────────────────────
$WheelVersion = ""
try {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [System.IO.Compression.ZipFile]::OpenRead($WheelFile)
    $metadataEntry = $zip.Entries | Where-Object { $_.FullName -match '\.dist-info/METADATA$' } | Select-Object -First 1
    if ($metadataEntry) {
        $reader = New-Object System.IO.StreamReader($metadataEntry.Open())
        $content = $reader.ReadToEnd()
        $reader.Close()
        if ($content -match '(?m)^Version:\s*(.+)') {
            $WheelVersion = $Matches[1].Trim()
        }
    }
    $zip.Dispose()
} catch {}
if (-not $WheelVersion) {
    $WheelVersion = if ($WheelFile -match 'luna-(\d+\.\d+\.\d+)-') { $matches[1] } else { "0.0.0" }
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

# ── 2. Install to dedicated venv (增量更新) ──────────────
Write-Step "Installing Luna"

$VenDir = Join-Path $env:USERPROFILE ".Luna"
$Pip = Join-Path $VenDir "Scripts\pip.exe"
if (Test-Path $VenDir) {
    # 获取已安装版本
    try {
        $InstalledVer = & "$VenDir\Scripts\python.exe" -c "from __version__ import __version__; print(__version__)" 2>$null
    } catch {
        $InstalledVer = "0.0.0"
    }
    Write-Info "已安装版本: $InstalledVer"
    Write-Info "目标版本:   $WheelVersion"

    if ($InstalledVer -eq $WheelVersion) {
        Write-Info "已是最新版本，无需更新"
    } else {
        Write-Info "更新: $InstalledVer → $WheelVersion"
        $pipResult = & $Pip install --upgrade $WheelFile 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Error "pip install 失败:"
            Write-Error $pipResult
            exit 1
        }
        Write-Info "更新完成"
    }
} else {
    Write-Info "全新安装 Luna $WheelVersion ..."
    & $Python -m venv $VenDir | Out-Null
    $pipResult = & $Pip install $WheelFile 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Error "安装失败:"
        Write-Error $pipResult
        exit 1
    }
    Write-Info "已安装到 $VenDir"
}

# ── 2b. Install Rust agent runtime binary ──────────────
Write-Step "Installing Rust agent runtime"

$RustBin = Join-Path $VenDir "Scripts\luna-agent-runtime.exe"
if (Test-Path $RustBin) {
    Write-Info "Rust runtime 已安装，跳过"
} else {
    $Tag = if ($ReleaseData.tag_name) { $ReleaseData.tag_name } else { "v$WheelVersion" }
    $Arch = "x86_64-pc-windows-msvc"
    $ArchiveName = "luna-agent-runtime-${Arch}-${Tag}.zip"
    $RustUrl = "https://github.com/$Repo/releases/download/$Tag/$ArchiveName"

    Write-Info "Downloading Rust runtime: $ArchiveName"
    try {
        $RustZip = Join-Path $env:TEMP $ArchiveName
        Invoke-WebRequest -Uri $RustUrl -OutFile $RustZip -UseBasicParsing -ErrorAction Stop
        $RustTmp = Join-Path $env:TEMP "luna-runtime-extract"
        if (Test-Path $RustTmp) { Remove-Item $RustTmp -Recurse -Force }
        New-Item -ItemType Directory -Path $RustTmp -Force | Out-Null
        Expand-Archive -Path $RustZip -DestinationPath $RustTmp -Force
        $ExtractedBin = Get-ChildItem $RustTmp -Recurse -Filter "luna-agent-runtime.exe" | Select-Object -First 1
        if ($ExtractedBin) {
            Move-Item $ExtractedBin.FullName $RustBin -Force
            Write-Info "Rust runtime 已安装到 $RustBin"
        } else {
            Write-Warn "解压后未找到 luna-agent-runtime.exe"
        }
        Remove-Item $RustTmp -Recurse -Force
    } catch {
        Write-Warn "下载 Rust runtime 失败，Agent 将降级为纯 Python 模式: $_"
    }
}

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
            Write-Warn "npm install failed, will retry on first 'luna start'"
        }
        Pop-Location
    } else {
        Write-Warn "npm not found. Install Node.js (https://nodejs.org/) for best experience"
        Write-Warn "First 'luna start' will auto-install dependencies"
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

$BatPath = Join-Path $BinDir "luna.cmd"
$LunaExe = Join-Path $VenDir "Scripts\luna.exe"
"@echo off`r`n`"$LunaExe`" %*" | Set-Content -Path $BatPath
Write-Info "Created shortcut: $BatPath"

$BatPathLuna = Join-Path $BinDir "Luna.cmd"
$LunaExeLuna = Join-Path $VenDir "Scripts\Luna.exe"
"@echo off`r`n`"$LunaExeLuna`" %*" | Set-Content -Path $BatPathLuna
Write-Info "Created shortcut: $BatPathLuna"

# ── 5. Check PATH ──────────────────────────────────────────
Write-Step "Checking PATH"
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($UserPath -notlike "*$BinDir*") {
    Write-Warn "$BinDir not in PATH"
    Write-Host ""
    Write-Host "  Auto-adding to user environment variable PATH..."
    $newPath = $UserPath + ";" + $BinDir
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    Write-Info "Added. Restart your terminal for luna to be available"
} else {
    Write-Info "PATH already contains $BinDir"
}

# ── 6. Clean up old .local-pkgs files (dev setup residues) ────
Write-Step "Cleaning up old luna files"
$LocalPkgsDirs = @(
    "$env:USERPROFILE\code\luna\.local-pkgs",
    "$env:TEMP\luna-main\.local-pkgs"
)
foreach ($dir in $LocalPkgsDirs) {
    if (Test-Path $dir) {
        Write-Info "清理 $dir 中的旧 luna 文件..."
        $filesToRemove = @("cli.py", "__version__.py", "config.py", "luna.cmd", "Luna.cmd")
        foreach ($file in $filesToRemove) {
            $f = Join-Path $dir $file
            if (Test-Path $f) { Remove-Item $f -Force -ErrorAction SilentlyContinue }
        }
        $dirsToRemove = @("core", "api", "web")
        foreach ($d in $dirsToRemove) {
            $target = Join-Path $dir $d
            if (Test-Path $target) { Remove-Item $target -Recurse -Force -ErrorAction SilentlyContinue }
        }
        Get-ChildItem "$dir\luna-*.dist-info" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
        Write-Info "  ✅ 已清理"
    }
}

# ── Done ─────────────────────────────────────────────────────
Write-Step "Installation complete!"
Write-Host ""
Write-Host "  To get started:"
Write-Host ""
Write-Host "    mkdir my-kb; cd my-kb"
Write-Host "    luna init"
Write-Host "    luna start"
Write-Host ""
