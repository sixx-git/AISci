#!/bin/bash

# ============================================================================
# AI Scientist - 开发环境启动脚本 (Linux/Mac)
# 同时启动后端和前端
# ============================================================================

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=============================================${NC}"
echo -e "${BLUE}  AI Scientist - 启动开发环境${NC}"
echo -e "${BLUE}=============================================${NC}"
echo ""

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# 检查 .env 文件
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  警告: .env 文件不存在${NC}"
    echo -e "${YELLOW}正在从 .env.example 复制...${NC}"
    cp .env.example .env
    echo -e "${YELLOW}请编辑 .env 文件并重启${NC}"
    echo ""
fi

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}虚拟环境不存在，请先运行: scripts/setup_backend.sh${NC}"
    exit 1
fi

# 清理可能残留的进程
echo -e "${GREEN}清理旧进程...${NC}"
pkill -f "uvicorn.*app.main:app" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true
sleep 1

# 创建必要的目录
mkdir -p data storage storage/documents logs

echo ""
echo -e "${GREEN}=============================================${NC}"
echo -e "${GREEN}  启动后端服务...${NC}"
echo -e "${GREEN}=============================================${NC}"

# 激活虚拟环境并启动后端
source venv/bin/activate
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
cd ..

# 等待后端启动
echo -e "${GREEN}等待后端启动...${NC}"
sleep 3

# 检查后端是否启动成功
if kill -0 $BACKEND_PID 2>/dev/null; then
    echo -e "${GREEN}✅ 后端服务已启动: http://localhost:8000${NC}"
    echo -e "${GREEN}   API 文档: http://localhost:8000/docs${NC}"
else
    echo -e "${RED}❌ 后端服务启动失败${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}=============================================${NC}"
echo -e "${GREEN}  启动前端服务...${NC}"
echo -e "${GREEN}=============================================${NC}"

cd frontend
pnpm dev &
FRONTEND_PID=$!
cd ..

# 等待前端启动
sleep 3

if kill -0 $FRONTEND_PID 2>/dev/null; then
    echo -e "${GREEN}✅ 前端服务已启动: http://localhost:3000${NC}"
else
    echo -e "${RED}❌ 前端服务启动失败${NC}"
    kill $BACKEND_PID 2>/dev/null
    exit 1
fi

echo ""
echo -e "${BLUE}=============================================${NC}"
echo -e "${BLUE}  所有服务已启动!${NC}"
echo -e "${BLUE}=============================================${NC}"
echo ""
echo -e "${BLUE}  📊 后端 (FastAPI):${NC}"
echo -e "${BLUE}     - 地址: http://localhost:8000${NC}"
echo -e "${BLUE}     - API 文档: http://localhost:8000/docs${NC}"
echo -e "${BLUE}     - PID: $BACKEND_PID${NC}"
echo ""
echo -e "${BLUE}  🎨 前端 (React):${NC}"
echo -e "${BLUE}     - 地址: http://localhost:3000${NC}"
echo -e "${BLUE}     - PID: $FRONTEND_PID${NC}"
echo ""
echo -e "${YELLOW}按 Ctrl+C 停止所有服务${NC}"
echo ""

# 定义清理函数
cleanup() {
    echo ""
    echo -e "${YELLOW}正在停止服务...${NC}"
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    wait $BACKEND_PID 2>/dev/null
    wait $FRONTEND_PID 2>/dev/null
    echo -e "${GREEN}✅ 所有服务已停止${NC}"
    exit 0
}

# 捕获中断信号
trap cleanup SIGINT SIGTERM

# 等待进程
wait
