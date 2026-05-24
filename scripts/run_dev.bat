@echo off
REM ============================================================================
REM AI Scientist - 开发环境启动脚本 (Windows)
REM 同时启动后端和前端
REM ============================================================================

setlocal enabledelayedexpansion

echo =============================================
echo   AI Scientist - 启动开发环境
echo =============================================
echo.

REM 获取项目根目录
set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."
cd /d "%PROJECT_ROOT%"

REM 检查 .env 文件
if not exist ".env" (
    echo ⚠️  警告: .env 文件不存在
    echo 正在从 .env.example 复制...
    copy .env.example .env >nul
    echo 请编辑 .env 文件并重启
    echo.
)

REM 检查虚拟环境
if not exist "venv" (
    echo 虚拟环境不存在，请先运行: scripts\setup_backend.bat
    exit /b 1
)

REM 创建必要的目录
if not exist "data" mkdir data
if not exist "storage" mkdir storage
if not exist "storage\documents" mkdir storage\documents
if not exist "logs" mkdir logs

echo.
echo =============================================
echo   启动后端服务...
echo =============================================

REM 激活虚拟环境并启动后端
call venv\Scripts\activate.bat
cd backend
start "AI Scientist Backend" cmd /k "uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
cd ..

REM 等待后端启动
echo 等待后端启动...
timeout /t 5 /nobreak >nul

echo.
echo =============================================
echo   启动前端服务...
echo =============================================

cd frontend
start "AI Scientist Frontend" cmd /k "npm run dev"
cd ..

echo.
echo =============================================
echo   所有服务已启动!
echo =============================================
echo.
echo   📊 后端 (FastAPI):
echo      - 地址: http://localhost:8000
echo      - API 文档: http://localhost:8000/docs
echo.
echo   🎨 前端 (React):
echo      - 地址: http://localhost:3000
echo.
echo   注意: 服务已在新的控制台窗口中启动
echo   要停止服务，请关闭对应的窗口
echo.

REM 打开浏览器
timeout /t 2 /nobreak >nul
start http://localhost:3000

echo.
pause
