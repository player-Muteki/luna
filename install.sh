#!/usr/bin/env bash
# ============================================================
# Co-Thinker one-click install
#
# Usage:
#   bash install.sh                    # install from GitHub source
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

if [[ $# -ge 1 && -f "$1" ]]; then
    # Local .whl file
    WHEEL_PATH="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
else
    step "Downloading Co-Thinker from GitHub"
    TMP_DIR=$(mktemp -d)
    if command -v git &>/dev/null; then
        info "Cloning repo..."
        git clone --depth 1 "https://github.com/$REPO.git" "$TMP_DIR" --quiet
        info "Source cloned to $TMP_DIR"
    else
        info "Downloading zip..."
        ZIP_URL="https://github.com/$REPO/archive/refs/heads/main.zip"
        if command -v curl &>/dev/null; then
            curl -sSL --max-time 30 -o "/tmp/co-thinker.zip" "$ZIP_URL"
        else
            wget -q --timeout=30 -O "/tmp/co-thinker.zip" "$ZIP_URL"
        fi
        unzip -q "/tmp/co-thinker.zip" -d "/tmp/"
        TMP_DIR="/tmp/co-thinker-main"
        info "Source extracted to $TMP_DIR"
    fi
    WHEEL_PATH="$TMP_DIR"
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

# --- 3. Build web frontend ---
step "Building web frontend"
WEB_DIR=$("$VENV_DIR/bin/python" -c "import web, os; print(os.path.dirname(web.__file__))" 2>/dev/null || echo "")
if [[ -n "$WEB_DIR" && -f "$WEB_DIR/package.json" ]]; then
    if command -v npm &>/dev/null; then
        info "Installing frontend dependencies (npm install)..."
        if (cd "$WEB_DIR" && npm install --omit=dev) 2>&1; then
            info "Frontend deps installed"
            info "Building production bundle (npm run build)..."
            if (cd "$WEB_DIR" && npm run build) 2>&1; then
                info "Frontend built successfully"
            else
                warn "npm run build 失败，首次启动时自动构建"
            fi
        else
            warn "npm install 失败，首次 co-thinker start 时自动安装"
        fi
    else
        warn "npm 未安装 — 前端依赖将在首次 co-thinker start 时自动安装"
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
