#!/bin/bash

# ============================================================================
# AI Scientist - 后端设置脚本 (Linux/Mac)
# ============================================================================

set -e

echo "============================================="
echo "  AI Scientist - 后端设置"
echo "============================================="
echo ""

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# 1. 检查 Python
echo "[1/6] 检查 Python 版本..."
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 Python3，请先安装 Python 3.9+"
    exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "  Python 版本: $PYTHON_VERSION"
echo ""

# 2. 创建虚拟环境
echo "[2/6] 创建 Python 虚拟环境..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "  虚拟环境创建成功"
else
    echo "  虚拟环境已存在"
fi
echo ""

# 3. 激活虚拟环境
echo "[3/6] 激活虚拟环境..."
source venv/bin/activate
echo "  虚拟环境已激活"
echo ""

# 4. 升级 pip
echo "[4/6] 升级 pip..."
pip install --upgrade pip
echo ""

# 5. 安装依赖
echo "[5/6] 安装 Python 依赖..."
pip install -r requirements.txt
echo ""

# 6. 创建必要的目录
echo "[6/6] 创建必要的目录..."
mkdir -p data storage storage/documents logs
echo ""

# 检查 .env 文件
echo "============================================="
if [ ! -f ".env" ]; then
    echo "  提示: .env 文件不存在，正在从 .env.example 复制..."
    cp .env.example .env
    echo ""
    echo "  ⚠️  重要: 请编辑 .env 文件并填入你的配置!"
    echo "  特别是 QWEN_API_KEY 和 DATABASE_URL"
else
    echo "  ✅ .env 文件已存在"
fi
echo ""

echo "============================================="
echo "  后端设置完成!"
echo "============================================="
echo ""
echo "  下一步操作:"
echo "  1. 编辑 .env 文件配置你的设置"
echo "  2. 确保 MySQL 数据库已创建"
echo "  3. 运行: python scripts/init_db.py"
echo "  4. 运行: scripts/run_dev.sh"
echo ""
echo "  要激活虚拟环境: source venv/bin/activate"
echo ""
