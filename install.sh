#!/usr/bin/env bash
# ============================================================
# Lore one-click install
#
# Usage:
#   bash install.sh                    # install from GitHub Release (latest wheel)
#   bash install.sh co_thinker-*.whl  # local .whl file
# ============================================================
set -euo pipefail 2>/dev/null || set -eu

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'
info()  { echo -e "${GREEN}==>${NC} $1"; }
warn()  { echo -e "${YELLOW}==>${NC} $1"; }
error() { echo -e "${RED}==>${NC} $1"; }
step()  { echo -e "\n${BOLD}>> $1${NC}"; }

# --- Determine install source ---
REPO="player-Muteki/lore"
WHEEL_PATH=""

if [[ $# -ge 1 && -f "$1" ]]; then
    # Local .whl file
    WHEEL_PATH="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
    info "使用本地 wheel: $WHEEL_PATH"
else
    step "Downloading Lore from GitHub Release"

    TMP_DIR=$(mktemp -d)

    # Try to download wheel from GitHub Release via API
    if command -v curl &>/dev/null; then
        # 如有 GH_TOKEN 则附带认证，避免 API 速率限制
        GH_TOKEN="${GH_TOKEN:-${GITHUB_TOKEN:-}}"
        CURL_AUTH=""
        if [[ -n "$GH_TOKEN" ]]; then
            CURL_AUTH="-H \"Authorization: Bearer $GH_TOKEN\""
        fi
        API_OUT=$(curl -fsSL --max-time 15 $CURL_AUTH "https://api.github.com/repos/$REPO/releases/latest" 2>/dev/null || true)
        if [[ -n "$API_OUT" ]]; then
            # 优先用 Python 解析 JSON（更可靠），fallback 到 grep/sed
            if command -v python3 &>/dev/null; then
                PY_SCRIPT="import json,sys
data = json.loads(sys.stdin.read())
assets = data.get('assets', [])
for a in assets:
    if a.get('name','').endswith('.whl'):
        print(a.get('browser_download_url',''))
        break"
                WHEEL_URL=$(echo "$API_OUT" | python3 -c "$PY_SCRIPT" 2>/dev/null || true)
                TAG_NAME=$(echo "$API_OUT" | python3 -c "import json,sys; d=json.loads(sys.stdin.read()); print(d.get('tag_name',''))" 2>/dev/null || true)
            else
                WHEEL_URL=$(echo "$API_OUT" | grep -o '"browser_download_url": *"[^"]*\.whl"' | head -1 | sed 's/.*: *"//;s/"//' || true)
                TAG_NAME=$(echo "$API_OUT" | grep -o '"tag_name": *"[^"]*"' | head -1 | sed 's/.*: *"//;s/"//' || true)
            fi
            WHEEL_NAME=$(echo "$WHEEL_URL" | sed 's/.*\///' || true)
            if [[ -n "$WHEEL_URL" && -n "$WHEEL_NAME" ]]; then
                info "下载 wheel: $WHEEL_NAME (${TAG_NAME:-latest}) ..."
                WHEEL_FILE="$TMP_DIR/$WHEEL_NAME"
                curl -fsSL --max-time 60 -o "$WHEEL_FILE" "$WHEEL_URL" && WHEEL_PATH="$WHEEL_FILE"
            fi
        fi
    fi

    # Fallback: clone source and build locally
    if [[ -z "$WHEEL_PATH" ]]; then
        warn "GitHub Release 未找到 wheel，将从源码构建..."
        if command -v git &>/dev/null; then
            info "Cloning repo..."
            git clone --depth 1 "https://github.com/$REPO.git" "$TMP_DIR/repo" --quiet
            WHEEL_PATH="$TMP_DIR/repo"
            info "Source cloned to $TMP_DIR/repo"
        else
            info "Downloading zip..."
            ZIP_URL="https://github.com/$REPO/archive/refs/heads/main.zip"
            if command -v curl &>/dev/null; then
                curl -fsSL --max-time 30 -o "/tmp/Lore.zip" "$ZIP_URL"
            elif command -v wget &>/dev/null; then
                wget -q --timeout=30 -O "/tmp/Lore.zip" "$ZIP_URL"
            else
                error "需要 curl 或 wget 来下载安装包"
                exit 1
            fi
            unzip -q "/tmp/Lore.zip" -d "/tmp/" 2>/dev/null || {
                error "解压失败"
                exit 1
            }
            WHEEL_PATH="/tmp/Lore-main"
            info "Source extracted to $WHEEL_PATH"
        fi
    else
        info "wheel 下载完成"
    fi
fi

# --- Extract wheel version ---
WHEEL_VERSION=""
if [[ -n "$WHEEL_PATH" && "$WHEEL_PATH" == *.whl ]]; then
    WHEEL_VERSION=$(basename "$WHEEL_PATH" | sed -n 's/^co_thinker-\([0-9.]*\)-.*/\1/p')
fi
if [[ -z "$WHEEL_VERSION" ]]; then
    WHEEL_VERSION="0.0.0"
fi

# --- 1. Check Python ---
step "Checking Python"
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
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
    error "Python >= 3.10 required"
    exit 1
fi

# --- 2. Install to venv (增量更新) ---
step "Installing Lore"

VENV_DIR="$HOME/.Lore"
if [[ -d "$VENV_DIR" ]]; then
    # 获取已安装版本
    INSTALLED_VER=$("$VENV_DIR/bin/python" -c "from __version__ import __version__; print(__version__)" 2>/dev/null || echo "0.0.0")
    info "已安装版本: $INSTALLED_VER"
    info "目标版本:   $WHEEL_VERSION"

    # 比较版本号（简单字符串比较，适用于语义化版本）
    if [[ "$INSTALLED_VER" == "$WHEEL_VERSION" ]]; then
        info "已是最新版本，无需更新"
    else
        info "更新: $INSTALLED_VER → $WHEEL_VERSION"
        PYTHONPATH= "$VENV_DIR/bin/pip" install --upgrade "$WHEEL_PATH" --quiet || {
            error "pip install 失败"
            info "可尝试手动安装: $VENV_DIR/bin/pip install --upgrade $WHEEL_PATH"
            exit 1
        }
        info "更新完成"
    fi
else
    info "全新安装 Lore $WHEEL_VERSION ..."
    "$PYTHON" -m venv "$VENV_DIR"
    PYTHONPATH= "$VENV_DIR/bin/pip" install "$WHEEL_PATH" --quiet || {
        error "pip install 失败"
        exit 1
    }
    info "已安装到 $VENV_DIR"
fi

# --- 3. Install frontend dependencies ---
step "Installing web frontend dependencies"
WEB_DIR=$("$VENV_DIR/bin/python" -c "import web, os; print(os.path.dirname(web.__file__))" 2>/dev/null || echo "")
if [[ -n "$WEB_DIR" && -f "$WEB_DIR/package.json" ]]; then
    if command -v npm &>/dev/null; then
        info "安装前端依赖 (npm install)..."
        if (cd "$WEB_DIR" && npm install --quiet) 2>&1; then
            info "前端依赖安装完成"
        else
            warn "npm install 失败，首次 Lore start 时会自动安装"
        fi
    else
        warn "npm 未安装，首次 Lore start 时会自动安装"
        warn "推荐安装 Node.js (https://nodejs.org/) 以获得更快的启动体验"
    fi
else
    info "web 前端包未检测到，跳过前端构建"
fi

# --- 4. Create PATH link ---
step "Setting up PATH"

BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"

LINK="$BIN_DIR/Lore"
if [[ -L "$LINK" || -f "$LINK" ]]; then
    rm -f "$LINK"
fi
ln -s "$VENV_DIR/bin/Lore" "$LINK"
info "Created link: $LINK -> $VENV_DIR/bin/Lore"

# --- 5. Check PATH ---
step "Checking PATH"
SHELL_RC=""
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    warn "$BIN_DIR is not in PATH!"
    if [[ -f "$HOME/.zshrc" ]]; then
        SHELL_RC="$HOME/.zshrc"
    elif [[ -f "$HOME/.bashrc" ]]; then
        SHELL_RC="$HOME/.bashrc"
    elif [[ -f "$HOME/.bash_profile" ]]; then
        SHELL_RC="$HOME/.bash_profile"
    fi

    if [[ -n "$SHELL_RC" ]]; then
        echo "export PATH=\"\$PATH:$BIN_DIR\"" >> "$SHELL_RC"
        info "已添加到 $SHELL_RC"
    else
        echo "  Run: export PATH=\"\$PATH:$BIN_DIR\""
    fi
else
    info "PATH already includes $BIN_DIR"
fi

# --- 6. Clean up old Lore files in .local-pkgs ---
step "Cleaning up old Lore files"
# 如果 PYTHONPATH 中包含 .local-pkgs 目录，其中有老版本 Lore 文件，
# 会导致 import cli 加载旧版。这里遍历清理。
OLD_PYTHONPATH_DIRS=$(echo "${PYTHONPATH:-}" | tr ':' '\n' | grep '\.local-pkgs' | sort -u || true)
if [[ -z "$OLD_PYTHONPATH_DIRS" ]]; then
    # 找不到时也检查常见开发目录
    for dir in "$HOME/code/Lore/.local-pkgs" "/tmp/Lore-main/.local-pkgs"; do
        if [[ -d "$dir" ]]; then
            OLD_PYTHONPATH_DIRS="$OLD_PYTHONPATH_DIRS
$dir"
        fi
    done
fi
for dir in $OLD_PYTHONPATH_DIRS; do
    if [[ -d "$dir" ]]; then
        info "清理 $dir 中的旧 Lore 文件..."
        rm -f "$dir/cli.py" "$dir/__version__.py" "$dir/config.py"
        rm -rf "$dir/core" "$dir/api" "$dir/web"
        rm -rf "$dir/co_thinker-"*.dist-info
        info "  ✅ 已清理"
    fi
done

# --- 7. Cleanup ---
if [[ -n "${TMP_DIR:-}" && -d "$TMP_DIR" ]]; then
    rm -rf "$TMP_DIR"
fi

# --- Done ---
step "Installation complete!"
echo ""
echo "  mkdir my-kb && cd my-kb"
echo "  Lore init"
echo "  Lore start"
echo ""

# 提示用户加载 PATH
if [[ -n "$SHELL_RC" ]]; then
    echo ""
    warn "执行以下命令使 Lore 在当前终端生效："
    echo "  source $SHELL_RC"
    echo "  或直接运行: Lore"
fi
