#!/usr/bin/env bash
# ============================================================
# Co-Thinker one-click install
#
# Usage:
#   bash install.sh                    # install from GitHub Release (latest wheel)
#   bash install.sh co_thinker-*.whl  # local .whl file
# ============================================================
set -euo pipefail

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
REPO="player-Muteki/co-thinker"
WHEEL_PATH=""

if [[ $# -ge 1 && -f "$1" ]]; then
    # Local .whl file
    WHEEL_PATH="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
    info "使用本地 wheel: $WHEEL_PATH"
else
    step "Downloading Co-Thinker from GitHub Release"

    TMP_DIR=$(mktemp -d)

    # Use GitHub API to find the latest release wheel URL
    if command -v curl &>/dev/null; then
        API_OUT=$(curl -sSL --max-time 15 "https://api.github.com/repos/$REPO/releases/latest" 2>/dev/null || true)
        if [[ -n "$API_OUT" ]]; then
            # Extract the .whl asset download URL, tag name, and filename using grep/sed
            WHEEL_URL=$(echo "$API_OUT" | grep -o '"browser_download_url": *"[^"]*\.whl"' | head -1 | sed 's/.*: *"//;s/"//' || true)
            WHEEL_NAME=$(echo "$WHEEL_URL" | sed 's/.*\///' || true)
            TAG_NAME=$(echo "$API_OUT" | grep -o '"tag_name": *"[^"]*"' | head -1 | sed 's/.*: *"//;s/"//' || true)
            if [[ -n "$WHEEL_URL" && -n "$WHEEL_NAME" ]]; then
                info "下载 wheel: $WHEEL_NAME (${TAG_NAME:-latest}) ..."
                WHEEL_FILE="$TMP_DIR/$WHEEL_NAME"
                curl -sSL --max-time 60 -o "$WHEEL_FILE" "$WHEEL_URL" && WHEEL_PATH="$WHEEL_FILE"
            fi
        fi
    fi

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
                curl -sSL --max-time 30 -o "/tmp/co-thinker.zip" "$ZIP_URL"
            else
                wget -q --timeout=30 -O "/tmp/co-thinker.zip" "$ZIP_URL"
            fi
            unzip -q "/tmp/co-thinker.zip" -d "/tmp/"
            WHEEL_PATH="/tmp/co-thinker-main"
            info "Source extracted to $WHEEL_PATH"
        fi
    else
        info "wheel 下载完成"
    fi
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

# --- 2. Install to venv ---
step "Installing Co-Thinker"

VENV_DIR="$HOME/.co-thinker"
if [[ -d "$VENV_DIR" ]]; then
    warn "Removing existing installation at $VENV_DIR"
    rm -rf "$VENV_DIR"
fi

"$PYTHON" -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install "$WHEEL_PATH" --quiet
info "Installed to $VENV_DIR"

# --- 3. Install frontend dependencies ---
step "Installing web frontend dependencies"
WEB_DIR=$("$VENV_DIR/bin/python" -c "import web, os; print(os.path.dirname(web.__file__))" 2>/dev/null || echo "")
if [[ -n "$WEB_DIR" && -f "$WEB_DIR/package.json" ]]; then
    if command -v npm &>/dev/null; then
        info "安装前端依赖 (npm install)..."
        if (cd "$WEB_DIR" && npm install --quiet) 2>&1; then
            info "前端依赖安装完成"
        else
            warn "npm install 失败，首次 co-thinker start 时会自动安装"
        fi
    else
        warn "npm 未安装，首次 co-thinker start 时会自动安装"
        warn "推荐安装 Node.js (https://nodejs.org/) 以获得更快的启动体验"
    fi
else
    info "web 前端包未检测到，跳过前端构建"
fi

# --- 4. Create PATH link ---
step "Setting up PATH"

BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"

LINK="$BIN_DIR/co-thinker"
if [[ -L "$LINK" || -f "$LINK" ]]; then
    rm -f "$LINK"
fi
ln -s "$VENV_DIR/bin/co-thinker" "$LINK"
info "Created link: $LINK -> $VENV_DIR/bin/co-thinker"

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

# --- 6. Cleanup ---
if [[ -n "${TMP_DIR:-}" && -d "$TMP_DIR" ]]; then
    rm -rf "$TMP_DIR"
fi

# --- Done ---
step "Installation complete!"
echo ""
echo "  mkdir my-kb && cd my-kb"
echo "  co-thinker init"
echo "  co-thinker start"
echo ""

# 立即生效：重新加载终端配置
if [[ -n "$SHELL_RC" ]]; then
    exec "$SHELL" -l
fi
