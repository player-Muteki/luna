# Co-Thinker 一键安装脚本（Windows PowerShell）
# 从 GitHub 下载最新 .whl 包并安装到专用虚拟环境。
# 安装后 co-thinker 命令全局可用。
#
# 用法:
#   powershell -ExecutionPolicy Bypass -File install.ps1
#   powershell -ExecutionPolicy Bypass -File install.ps1 co_thinker-0.0.5-py3-none-any.whl
# 在线安装（无需下载）:
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
Write-Host "  Co-Thinker v0.0.5 - Windows 安装脚本"

# ── 参数处理：本地 .whl 或自动下载 ──────────────────────────
if ($WheelPath -and (Test-Path $WheelPath)) {
    $WheelFile = Resolve-Path $WheelPath
    Write-Info "使用本地文件: $WheelFile"
} else {
    Write-Step "从 GitHub 获取最新版本"
    $Repo = "player-Muteki/co-thinker"
    Write-Info "仓库: $Repo"

    $ApiUrl = "https://api.github.com/repos/$Repo/releases/latest"
    try {
        $ReleaseData = Invoke-RestMethod -Uri $ApiUrl -Headers @{ "Accept" = "application/json" }
    } catch {
        Write-Error "无法获取 Release 信息: $_"
        exit 1
    }

    $Asset = $ReleaseData.assets | Where-Object { $_.name -like "*.whl" } | Select-Object -First 1
    if (-not $Asset) {
        Write-Error "没有找到 .whl 发布文件"
        exit 1
    }

    $WheelUrl = $Asset.browser_download_url
    $WheelName = Split-Path $WheelUrl -Leaf
    $WheelFile = Join-Path $env:TEMP $WheelName
    Write-Info "下载: $WheelName"

    try {
        Invoke-WebRequest -Uri $WheelUrl -OutFile $WheelFile -UseBasicParsing
    } catch {
        Write-Error "下载失败: $_"
        exit 1
    }
    Write-Info "下载完成"
}

# ── 1. 检查 Python ──────────────────────────────────────────
Write-Step "检查 Python"
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
    Write-Error "需要 Python >= 3.10"
    exit 1
}

# ── 2. 安装到专用虚拟环境 ───────────────────────────────────
Write-Step "安装 Co-Thinker"

$VenDir = Join-Path $env:USERPROFILE ".co-thinker"
if (Test-Path $VenDir) {
    Write-Warn "已存在 $VenDir，重新安装"
    Remove-Item -Recurse -Force $VenDir
}

& $Python -m venv $VenDir | Out-Null
$Pip = Join-Path $VenDir "Scripts\pip.exe"
& $Pip install $WheelFile --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Error "安装失败"
    exit 1
}
Write-Info "已安装到 $VenDir"

# ── 3. 创建 PATH 快捷入口 ──────────────────────────────────
Write-Step "配置系统路径"

$BinDir = Join-Path $env:USERPROFILE ".local\bin"
if (-not (Test-Path $BinDir)) {
    New-Item -ItemType Directory -Path $BinDir -Force | Out-Null
}

$BatPath = Join-Path $BinDir "co-thinker.cmd"
$CoThinkerExe = Join-Path $VenDir "Scripts\co-thinker.exe"
$batContent = "@echo off`r`n`"$CoThinkerExe`" %*"
$batContent | Set-Content -Path $BatPath
Write-Info "已创建入口: $BatPath"

# ── 4. 检查 PATH ────────────────────────────────────────────
Write-Step "检查 PATH"
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($UserPath -notlike "*$BinDir*") {
    Write-Warn "$BinDir 不在 PATH 中"
    Write-Host ""
    Write-Host "  自动添加到用户环境变量 PATH..."
    $newPath = $UserPath + ";" + $BinDir
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    Write-Info "已添加，请重新打开终端后 co-thinker 命令即可使用"
} else {
    Write-Info "PATH 已包含 $BinDir"
}

# ── 完成 ──────────────────────────────────────────────────────
Write-Step "安装完成！"
Write-Host ""
Write-Host "  运行以下命令开始使用："
Write-Host ""
Write-Host "    mkdir my-kb && cd my-kb"
Write-Host "    co-thinker init       # 创建 .env 和运行时目录"
Write-Host "    co-thinker start      # 启动 Web 界面"
Write-Host ""
