#!/bin/bash

# ============================================================================
# AI Scientist - 后端设置脚本 (Linux/Mac)
# ============================================================================

set -e

echo "============================================="
echo "  AI Scientist - 后端设置"
echo "============================================="
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo "[1/6] 检查 Python 版本..."
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 Python3，请先安装 Python 3.10 / 3.11 / 3.12（推荐）"
    exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "  Python 版本: $PYTHON_VERSION"
echo ""

echo "[2/6] 创建 Python 虚拟环境..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "  虚拟环境创建成功"
else
    echo "  虚拟环境已存在"
fi
echo ""

echo "[3/6] 激活虚拟环境..."
# shellcheck source=/dev/null
source venv/bin/activate
echo "  虚拟环境已激活"
echo ""

echo "[4/6] 升级 pip..."
pip install --upgrade pip
echo ""

echo "[5/6] 安装 Python 依赖..."
if [ ! -f "backend/requirements.txt" ]; then
    echo "错误: 未找到 backend/requirements.txt"
    exit 1
fi
pip install -r backend/requirements.txt
echo ""

echo "[6/6] 创建必要的目录..."
mkdir -p data backend/data storage storage/documents storage/pingfenbiao_jobs logs
echo ""

echo "============================================="
if [ ! -f "backend/.env" ]; then
    if [ -f ".env" ]; then
        echo "  正在复制根目录 .env -> backend/.env ..."
        cp .env backend/.env
    elif [ -f ".env.example" ]; then
        echo "  正在从 .env.example 创建 backend/.env ..."
        cp .env.example backend/.env
        [ -f ".env" ] || cp .env.example .env
        echo ""
        echo "  请编辑 backend/.env 并填入 QWEN_API_KEY（或设 USE_MOCK_LLM=true）"
    else
        echo "  警告: 未找到 .env.example，请手动创建 backend/.env"
    fi
else
    echo "  backend/.env 已存在（后端实际读取此文件）"
fi
echo ""

echo "============================================="
echo "  后端设置完成!"
echo "============================================="
echo ""
echo "  下一步:"
echo "  1. 编辑 backend/.env（默认 SQLite，无需 MySQL）"
echo "  2. 可选: python scripts/init_db.py"
echo "  3. 启动: scripts/run_dev.sh"
echo ""
echo "  激活虚拟环境: source venv/bin/activate"
echo ""
