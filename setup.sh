#!/usr/bin/env bash
# ============================================================
# Lore dev environment setup
# Run after cloning: bash setup.sh
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

# --- 1. Check Python version ---
step "Checking Python"

PYTHON=""
REQUIRED_MAJOR=3
REQUIRED_MINOR=10

for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?')
        major=${ver%%.*}
        minor=${ver#*.}
        minor=${minor%%.*}
        if [[ "$major" -gt "$REQUIRED_MAJOR" ]] || \
           [[ "$major" -eq "$REQUIRED_MAJOR" && "$minor" -ge "$REQUIRED_MINOR" ]]; then
            PYTHON="$cmd"
            info "Python $("$cmd" --version 2>&1)"
            break
        fi
    fi
done

if [[ -z "$PYTHON" ]]; then
    error "Python >= 3.10 required (recommended: 3.12)"
    echo "  Ubuntu/Debian: sudo apt install python3 python3-venv python3-pip"
    echo "  macOS:         brew install python@3.12"
    echo "  or pyenv:      pyenv install 3.12.3"
    exit 1
fi

# --- 2. Create virtual environment ---
step "Creating virtual environment (.venv)"
if [[ -d .venv ]]; then
    warn ".venv already exists, skipping"
else
    "$PYTHON" -m venv .venv
    info ".venv created"
fi

source .venv/bin/activate

# --- 3. Install dependencies ---
step "Installing dependencies"
pip install --upgrade pip -q

if [[ -f requirements.lock ]]; then
    pip install -r requirements.lock -q
    info "Installed from requirements.lock (pinned)"
else
    pip install -r requirements.txt -q
    info "Installed from requirements.txt (minimum versions)"
    warn "No requirements.lock found; versions may differ"
    warn "Run 'pip freeze > requirements.lock' to pin"
fi

# --- 4. Create runtime directories ---
step "Creating runtime directories"
mkdir -p vectorstore storage
info "vectorstore/ storage/ ready"

# --- 5. Install web frontend dependencies ---
step "Installing web frontend dependencies"
if [[ -d web ]]; then
    if [[ ! -d web/node_modules ]]; then
        if command -v npm &>/dev/null; then
            info "Running npm install in web/ ..."
            (cd web && npm install --quiet) && info "Web frontend dependencies installed" || \
                warn "npm install 失败，可稍后运行 lore start 自动安装"
        else
            warn "npm not found! Install Node.js first (https://nodejs.org/)"
            warn "Or run 'lore start' later — it will auto-install deps"
        fi
    else
        info "web/node_modules/ already exists, skipping"
    fi
else
    info "web/ directory not found, skipping frontend setup"
fi

# --- 6. Verify ---
step "Verifying"
python -c "
from config import load_settings, validate_settings
s = load_settings()
validate_settings(s)
print('  Config OK')
" 2>&1 | tail -1

# --- Done ---
step "Dev environment ready!"
echo ""
echo "  Activate:     source .venv/bin/activate"
echo "  Start:        lore start"
echo "  Test:         pytest tests/ -v"
echo "  Dependencies: pip list"
