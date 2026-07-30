#!/bin/bash

# ============================================================================
# AI Scientist - 前端设置脚本 (Linux/Mac)
# ============================================================================

set -e

echo "============================================="
echo "  AI Scientist - 前端设置"
echo "============================================="
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT/frontend"

echo "[1/4] 检查 Node.js 版本..."
if ! command -v node &> /dev/null; then
    echo "错误: 未找到 Node.js，请先安装 Node.js 18+"
    echo "下载地址: https://nodejs.org/"
    exit 1
fi

NODE_VERSION=$(node -v)
echo "  Node.js 版本: $NODE_VERSION"

if ! command -v pnpm &> /dev/null; then
    echo "错误: 未找到 pnpm。可执行: npm install -g pnpm"
    exit 1
fi
PNPM_VERSION=$(pnpm -v)
echo "  pnpm 版本: $PNPM_VERSION"
echo ""

echo "[2/4] 检查 package.json..."
if [ ! -f "package.json" ]; then
    echo "错误: 未找到 package.json 文件"
    exit 1
fi
echo "  package.json 已存在"
echo ""

echo "[3/4] 安装 pnpm 依赖..."
pnpm install
echo "  依赖安装完成"
echo ""

echo "[4/4] 检查开发环境..."
echo "  前端准备就绪"
echo ""

echo "============================================="
echo "  前端设置完成!"
echo "============================================="
echo ""
echo "  下一步:"
echo "  1. 确保后端服务正在运行 (http://localhost:8000)"
echo "  2. 运行: scripts/run_dev.sh"
echo "  3. 或仅启动前端: cd frontend && pnpm dev"
echo ""
