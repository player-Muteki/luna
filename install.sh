#!/usr/bin/env bash
# ============================================================
# Co-Thinker 一键安装
#
# 用法:
#   bash install.sh                    # 自动从 GitHub 下载最新版
#   bash install.sh co_thinker-0.0.2-py3-none-any.whl  # 本地安装
#
# 安装后 co-thinker 命令全局可用。
# ============================================================
set -euo pipefail

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'
info()  { echo -e "${GREEN}✓${NC} $1"; }
warn()  { echo -e "${YELLOW}⚠${NC} $1"; }
error() { echo -e "${RED}✗${NC} $1"; }
step()  { echo -e "\n${BOLD}▶ $1${NC}"; }

# ── 可选：从 GitHub 自动下载 ───────────────────────────────
REPO="player-Muteki/co-thinker"

if [[ $# -ge 1 && -f "$1" ]]; then
    WHEEL_PATH="$(realpath "$1")"
elif [[ $# -eq 0 ]]; then
    step "从 GitHub 获取最新版本"
    info "仓库: $REPO"
    API_URL="https://api.github.com/repos/$REPO/releases/latest"
    if command -v curl &>/dev/null; then
        RELEASE_DATA=$(curl -s "$API_URL")
    elif command -v wget &>/dev/null; then
        RELEASE_DATA=$(wget -q -O- "$API_URL")
    else
        error "需要 curl 或 wget"
        exit 1
    fi
    # 查找 .whl 文件下载链接
    WHEEL_URL=$(echo "$RELEASE_DATA" | grep -oP 'https://[^"]+\.whl' | head -1)
    if [[ -z "$WHEEL_URL" ]]; then
        error "没有找到 .whl 发布文件"
        exit 1
    fi
    WHEEL_NAME=$(basename "$WHEEL_URL")
    info "下载: $WHEEL_NAME"
    if command -v curl &>/dev/null; then
        curl -sSL -o "/tmp/$WHEEL_NAME" "$WHEEL_URL"
    else
        wget -q -O "/tmp/$WHEEL_NAME" "$WHEEL_URL"
    fi
    WHEEL_PATH="/tmp/$WHEEL_NAME"
    info "下载完成"
else
    echo "用法:"
    echo "  bash install.sh                        # 自动下载并安装"
    echo "  bash install.sh co_thinker-0.0.2-...   # 从本地 .whl 安装"
    exit 1
fi

# ── 1. 检查 Python ──────────────────────────────────────────
step "检查 Python"
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" --version 2>&1 | grep -oP '\d+\.\d+')
        major="${ver%.*}"
        minor="${ver#*.}"
        if [[ "$major" -ge 3 && "$minor" -ge 10 ]]; then
            PYTHON="$cmd"
            info "Python $("$cmd" --version 2>&1)"
            break
        fi
    fi
done
if [[ -z "$PYTHON" ]]; then
    error "需要 Python >= 3.10"
    exit 1
fi

# ── 2. 安装到专用虚拟环境 ───────────────────────────────────
step "安装 Co-Thinker"

VENV_DIR="$HOME/.co-thinker"
if [[ -d "$VENV_DIR" ]]; then
    warn "已存在 $VENV_DIR，重新安装"
    rm -rf "$VENV_DIR"
fi

"$PYTHON" -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install "$WHEEL_PATH" --quiet
info "已安装到 $VENV_DIR"

# ── 3. 创建 PATH 链接 ──────────────────────────────────────
step "配置系统路径"

# 确保目标 bin 目录存在
BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"

LINK="$BIN_DIR/co-thinker"
if [[ -L "$LINK" || -f "$LINK" ]]; then
    rm -f "$LINK"
fi
ln -s "$VENV_DIR/bin/co-thinker" "$LINK"
info "已创建链接: $LINK -> $VENV_DIR/bin/co-thinker"

# ── 4. 检查 PATH ────────────────────────────────────────────
step "检查 PATH"
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    warn "$BIN_DIR 不在 PATH 中！"
    echo ""
    echo "  将以下内容添加到 ~/.bashrc 或 ~/.zshrc:"
    echo ""
    echo "    export PATH=\"\$PATH:$BIN_DIR\""
    echo ""
    echo "  然后执行: source ~/.zshrc"
    echo ""
else
    info "PATH 已包含 $BIN_DIR"
fi

# ── 完成 ──────────────────────────────────────────────────────
step "✅ 安装完成！"
echo ""
echo "  运行以下命令开始使用："
echo ""
echo "    mkdir my-kb && cd my-kb"
echo "    co-thinker init       # 创建 .env 和运行时目录"
echo "    co-thinker start      # 启动 Web 界面"
echo ""
