#!/usr/bin/env bash
# Lore 外部安装产物一键卸载
# 运行方式: bash scripts/uninstall.sh
# 说明: 只清理系统级安装产物，不动 code/lore/ 源码目录
set -e

echo "==> 清理 ~/.lore/（全局虚拟环境）"
rm -rf ~/.lore/

echo "==> 清理 ~/.lorerc（全局配置）"
rm -f ~/.lorerc

echo "==> 清理 ~/.local/bin/lore（PATH 入口）"
rm -f ~/.local/bin/lore

echo "==> 清理 ~/.cargo/bin/lore"
rm -f ~/.cargo/bin/lore

echo "==> 清理 ~/.cache/lore"
rm -f ~/.cache/lore

echo "==> 清理 PYTHONPATH 环境变量"
unset PYTHONPATH

echo ""
echo "[DONE] 所有外部安装产物已清除，源码目录保持不动"
