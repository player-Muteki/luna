#!/usr/bin/env bash
# ============================================================
# Co-Thinker 开发环境一键设置
# 克隆仓库后运行: bash setup.sh
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

# ── 1. 检查 Python 版本 ──────────────────────────────────────
step "检查 Python"

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
    error "需要 Python >= 3.10 (推荐 3.12)"
    echo "  Ubuntu/Debian: sudo apt install python3 python3-venv python3-pip"
    echo "  macOS:         brew install python@3.12"
    echo "  或使用 pyenv:  pyenv install 3.12.3"
    exit 1
fi

# ── 2. 创建虚拟环境 ──────────────────────────────────────────
step "创建虚拟环境 (.venv)"
if [[ -d .venv ]]; then
    warn ".venv 已存在，跳过"
else
    "$PYTHON" -m venv .venv
    info "已创建 .venv"
fi

source .venv/bin/activate

# ── 3. 安装依赖 ──────────────────────────────────────────────
step "安装依赖"
pip install --upgrade pip -q

if [[ -f requirements.lock ]]; then
    # 精确版本锁定，确保完全一致
    pip install -r requirements.lock -q
    info "已从 requirements.lock 安装（精确版本锁定）"
else
    # 无 lock 文件则从 requirements.txt 安装（仅版本下限）
    pip install -r requirements.txt -q
    info "已从 requirements.txt 安装（版本下限）"
    warn "提示: 无 requirements.lock，版本可能与你不同"
    warn "运行 'pip freeze > requirements.lock' 可创建版本锁"
fi

# ── 4. 创建运行时目录 ────────────────────────────────────────
step "创建运行时目录"
mkdir -p vectorstore storage
info "vectorstore/ storage/ 已就绪"

# ── 5. 验证 ──────────────────────────────────────────────────
step "验证"
python -c "
from config import load_settings, validate_settings
s = load_settings()
validate_settings(s)
print('  ✓ 配置接口正常')
" 2>&1 | tail -1

# ── 完成 ──────────────────────────────────────────────────────
step "✅ 开发环境就绪！"
echo ""
echo "  激活环境:  source .venv/bin/activate"
echo "  启动应用:  streamlit run app/streamlit_app.py"
echo "  运行测试:  pytest tests/ -v"
echo "  查看依赖:  pip list"
