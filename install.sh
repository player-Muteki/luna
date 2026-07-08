#!/usr/bin/env bash
# ============================================================
# Co-Thinker one-click install
#
# Usage:
#   bash install.sh                    # auto-download from GitHub
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

# --- Download from GitHub ---
REPO="player-Muteki/co-thinker"

if [[ $# -ge 1 && -f "$1" ]]; then
    WHEEL_PATH="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
elif [[ $# -eq 0 ]]; then
    step "Fetching latest release from GitHub"
    info "Repo: $REPO"
    API_URL="https://api.github.com/repos/$REPO/releases/latest"
    if command -v curl &>/dev/null; then
        RELEASE_DATA=$(curl -s --max-time 10 "$API_URL")
    elif command -v wget &>/dev/null; then
        RELEASE_DATA=$(wget -q --timeout=10 -O- "$API_URL")
    else
        error "curl or wget required"
        exit 1
    fi

    # 检查 API 是否返回了有效的 release 数据（被限流时返回的 JSON 不含 assets）
    HAS_RELEASE=$(echo "$RELEASE_DATA" | grep -c '"tag_name"' || true)
    WHEEL_URL=$(echo "$RELEASE_DATA" | grep -oE 'https://[^"\\]+\.whl' | head -1)
    if [[ -n "$WHEEL_URL" && "$HAS_RELEASE" -gt 0 ]]; then
        WHEEL_NAME=$(basename "$WHEEL_URL")
        info "Downloading: $WHEEL_NAME"
        if command -v curl &>/dev/null; then
            curl -sSL -o "/tmp/$WHEEL_NAME" "$WHEEL_URL"
        else
            wget -q -O "/tmp/$WHEEL_NAME" "$WHEEL_URL"
        fi
        WHEEL_PATH="/tmp/$WHEEL_NAME"
        info "Download complete"
    else
        warn "No .whl release found, installing from source"
        TMP_DIR=$(mktemp -d)
        if command -v git &>/dev/null; then
            git clone --depth 1 "$REPO" "$TMP_DIR" --quiet 2>/dev/null || \
            git clone --depth 1 "https://github.com/$REPO.git" "$TMP_DIR" --quiet
        else
            ZIP_URL="https://github.com/$REPO/archive/refs/heads/main.zip"
            if command -v curl &>/dev/null; then
                curl -sSL -o "/tmp/co-thinker.zip" "$ZIP_URL"
            else
                wget -q -O "/tmp/co-thinker.zip" "$ZIP_URL"
            fi
            unzip -q "/tmp/co-thinker.zip" -d "/tmp/"
            TMP_DIR="/tmp/co-thinker-main"
        fi
        info "Source downloaded to $TMP_DIR"
        WHEEL_PATH="$TMP_DIR"
    fi
else
    echo "Usage:"
    echo "  bash install.sh                        # auto-download"
    echo "  bash install.sh co_thinker-*.whl       # local install"
    exit 1
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

# --- 3. Create PATH link ---
step "Setting up PATH"

BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"

LINK="$BIN_DIR/co-thinker"
if [[ -L "$LINK" || -f "$LINK" ]]; then
    rm -f "$LINK"
fi
ln -s "$VENV_DIR/bin/co-thinker" "$LINK"
info "Created link: $LINK -> $VENV_DIR/bin/co-thinker"

# --- 4. Check PATH ---
step "Checking PATH"
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    warn "$BIN_DIR is not in PATH!"
    echo ""
    echo "  Add the following to ~/.bashrc or ~/.zshrc:"
    echo ""
    echo "    export PATH=\"\$PATH:$BIN_DIR\""
    echo ""
    echo "  Then run: source ~/.zshrc"
    echo ""
else
    info "PATH already includes $BIN_DIR"
fi

# --- Done ---
step "Installation complete!"
echo ""
echo "  Create a working directory and start:"
echo ""
echo "    mkdir my-kb && cd my-kb"
echo "    co-thinker init"
echo "    co-thinker start"
echo ""
