#!/bin/bash

# ============================================================================
# AI Scientist - 开发环境启动脚本 (Linux/Mac)
# 对齐 Windows launch_stack.bat quick：Backend + Frontend
# ============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=============================================${NC}"
echo -e "${BLUE}  AI Scientist - 启动开发环境 (quick)${NC}"
echo -e "${BLUE}=============================================${NC}"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

VENV_PY="$PROJECT_ROOT/venv/bin/python"
if [ ! -x "$VENV_PY" ]; then
    echo -e "${YELLOW}虚拟环境不存在，请先运行: scripts/setup_backend.sh${NC}"
    exit 1
fi

# 后端优先读 backend/.env
if [ ! -f "backend/.env" ]; then
    if [ -f ".env" ]; then
        echo -e "${YELLOW}复制根目录 .env -> backend/.env ...${NC}"
        cp .env backend/.env
    elif [ -f ".env.example" ]; then
        echo -e "${YELLOW}从 .env.example 创建 backend/.env ...${NC}"
        cp .env.example backend/.env
        echo -e "${YELLOW}请编辑 backend/.env 后如需可重启${NC}"
    else
        echo -e "${YELLOW}警告: 未找到 .env，后端可能缺少 QWEN_API_KEY${NC}"
    fi
fi

mkdir -p data backend/data storage storage/documents storage/pingfenbiao_jobs logs

wait_url() {
    local url="$1"
    local max_sec="${2:-60}"
    local i=0
    while [ "$i" -lt "$max_sec" ]; do
        if curl -fsS -o /dev/null --connect-timeout 2 "$url" 2>/dev/null; then
            return 0
        fi
        sleep 2
        i=$((i + 2))
    done
    return 1
}

# 端口占用则复用（不强制杀进程，避免误伤）
if curl -fsS -o /dev/null --connect-timeout 2 "http://127.0.0.1:8000/health" 2>/dev/null; then
    echo -e "${GREEN}[OK] Backend already healthy on :8000${NC}"
else
    echo -e "${GREEN}启动后端服务...${NC}"
    (
        cd "$PROJECT_ROOT/backend"
        exec "$VENV_PY" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
    ) &
    BACKEND_PID=$!
    echo -e "${GREEN}等待后端 /health ...${NC}"
    if ! wait_url "http://127.0.0.1:8000/health" 90; then
        echo -e "${RED}后端未在时限内就绪 (PID=$BACKEND_PID)${NC}"
        kill "$BACKEND_PID" 2>/dev/null || true
        exit 1
    fi
    echo -e "${GREEN}[OK] Backend is up${NC}"
fi

if curl -fsS -o /dev/null --connect-timeout 2 "http://127.0.0.1:5173/" 2>/dev/null; then
    echo -e "${GREEN}[OK] Frontend already responding on :5173${NC}"
else
    if ! command -v pnpm &> /dev/null; then
        echo -e "${RED}错误: 未找到 pnpm${NC}"
        exit 1
    fi
    echo -e "${GREEN}启动前端服务...${NC}"
    (
        cd "$PROJECT_ROOT/frontend"
        exec pnpm dev
    ) &
    FRONTEND_PID=$!
    echo -e "${GREEN}等待前端...${NC}"
    if ! wait_url "http://127.0.0.1:5173/" 60; then
        echo -e "${RED}前端未在时限内就绪${NC}"
        [ -n "${BACKEND_PID:-}" ] && kill "$BACKEND_PID" 2>/dev/null || true
        kill "$FRONTEND_PID" 2>/dev/null || true
        exit 1
    fi
    echo -e "${GREEN}[OK] Frontend is up${NC}"
fi

echo ""
echo -e "${BLUE}=============================================${NC}"
echo -e "${BLUE}  服务已就绪${NC}"
echo -e "${BLUE}=============================================${NC}"
echo -e "  Backend:  http://localhost:8000"
echo -e "  API Docs: http://localhost:8000/docs"
echo -e "  Frontend: http://localhost:5173"
echo ""
echo -e "${YELLOW}按 Ctrl+C 停止本脚本拉起的服务${NC}"
echo ""

cleanup() {
    echo ""
    echo -e "${YELLOW}正在停止服务...${NC}"
    [ -n "${BACKEND_PID:-}" ] && kill "$BACKEND_PID" 2>/dev/null || true
    [ -n "${FRONTEND_PID:-}" ] && kill "$FRONTEND_PID" 2>/dev/null || true
    wait 2>/dev/null || true
    echo -e "${GREEN}已停止${NC}"
    exit 0
}
trap cleanup SIGINT SIGTERM

# 若两个服务都是复用已有进程，则脚本可直接退出；否则 wait
if [ -n "${BACKEND_PID:-}" ] || [ -n "${FRONTEND_PID:-}" ]; then
    wait
else
    echo -e "${YELLOW}前后端均为已有进程，脚本退出（不关闭它们）。${NC}"
fi
