#!/usr/bin/env bash
# Co-Thinker 开发模式启动脚本
# 设置 PYTHONPATH 指向源码，使修复生效（site-packages 为只读文件系统时可用）
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="${SCRIPT_DIR}${PYTHONPATH:+:$PYTHONPATH}"

exec /home/kys/.co-thinker/bin/co-thinker "$@"
