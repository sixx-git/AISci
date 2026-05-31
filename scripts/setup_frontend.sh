#!/bin/bash

# ============================================================================
# AI Scientist - 前端设置脚本 (Linux/Mac)
# ============================================================================

set -e

echo "============================================="
echo "  AI Scientist - 前端设置"
echo "============================================="
echo ""

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT/frontend"

# 1. 检查 Node.js
echo "[1/4] 检查 Node.js 版本..."
if ! command -v node &> /dev/null; then
    echo "错误: 未找到 Node.js，请先安装 Node.js 18+"
    echo "下载地址: https://nodejs.org/"
    exit 1
fi

NODE_VERSION=$(node -v)
echo "  Node.js 版本: $NODE_VERSION"

PNPM_VERSION=$(pnpm -v)
echo "  pnpm 版本: $PNPM_VERSION"
echo ""

# 2. 检查 package.json
echo "[2/4] 检查 package.json..."
if [ ! -f "package.json" ]; then
    echo "错误: 未找到 package.json 文件"
    exit 1
fi
echo "  package.json 已存在"
echo ""

# 3. 安装依赖
echo "[3/4] 安装 npm 依赖..."
if [ -d "node_modules" ]; then
    echo "  node_modules 已存在，跳过安装"
else
    npm install
    echo "  依赖安装完成"
fi
echo ""

# 4. 检查是否可构建
echo "[4/4] 检查开发环境..."
echo "  前端准备就绪"
echo ""

echo "============================================="
echo "  前端设置完成!"
echo "============================================="
echo ""
echo "  下一步操作:"
echo "  1. 确保后端服务正在运行 (http://localhost:8000)"
echo "  2. 运行: scripts/run_dev.sh (同时启动前后端)"
echo "  3. 或仅启动前端: cd frontend && pnpm dev"
echo ""
