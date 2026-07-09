#!/usr/bin/env bash
# Co-Thinker 外部安装产物一键卸载
# 运行方式: bash scripts/uninstall.sh
# 说明: 只清理系统级安装产物，不动 code/co-thinker/ 源码目录
set -e

echo "==> 清理 ~/.co-thinker/（全局虚拟环境）"
rm -rf ~/.co-thinker/

echo "==> 清理 ~/.co-thinkerc（全局配置）"
rm -f ~/.co-thinkerc

echo "==> 清理 ~/.local/bin/co-thinker（PATH 入口）"
rm -f ~/.local/bin/co-thinker

echo "==> 清理 ~/.cargo/bin/co-thinker"
rm -f ~/.cargo/bin/co-thinker

echo "==> 清理 ~/.cache/co-thinker"
rm -f ~/.cache/co-thinker

echo "==> 清理 PYTHONPATH 环境变量"
unset PYTHONPATH

echo ""
echo "[DONE] 所有外部安装产物已清除，code/co-thinker/ 源码保持不动"
