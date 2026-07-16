@echo off
REM ============================================================================
REM AI Scientist - 完整环境启动脚本 (Windows)
REM 同时启动：后端 + 前端 + pingfenbiao
REM ============================================================================

setlocal enabledelayedexpansion

echo =============================================
echo   AI Scientist - 完整环境启动
echo =============================================
echo.

set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."
cd /d "%PROJECT_ROOT%"

if not exist ".env" (
    echo ⚠️  警告: .env 文件不存在
    echo 正在从 .env.example 复制...
    copy .env.example .env >nul
    echo 请编辑 .env 文件并重启
    echo.
)

if not exist "venv" (
    echo 虚拟环境不存在，请先运行: scripts\setup_backend.bat
    exit /b 1
)

if not exist "data" mkdir data
if not exist "storage" mkdir storage
if not exist "storage\documents" mkdir storage\documents
if not exist "logs" mkdir logs

echo.
echo =============================================
echo   启动后端服务...
echo =============================================

call venv\Scripts\activate.bat
cd backend
start "AI Scientist Backend" cmd /k "uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
cd ..

echo 等待后端启动...
timeout /t 5 /nobreak >nul

echo.
echo =============================================
echo   启动评分表服务 (pingfenbiao)...
echo =============================================

if exist "pingfenbiao-main\pingfenbiao-main\web\app.py" (
    cd pingfenbiao-main\pingfenbiao-main\web
    start "Pingfenbiao Service" cmd /k "uvicorn app:app --host 127.0.0.1 --port 8765"
    cd ..\..\..
) else (
    echo ⚠️  pingfenbiao 未找到，跳过启动
    echo    如需使用预测功能，请克隆 pingfenbiao 仓库到 pingfenbiao-main/
)

echo 等待评分表服务启动...
timeout /t 3 /nobreak >nul

echo.
echo =============================================
echo   启动前端服务...
echo =============================================

cd frontend
start "AI Scientist Frontend" cmd /k "pnpm dev"
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
echo   📈 评分表服务 (pingfenbiao):
echo      - 地址: http://localhost:8765
echo.
echo   🎨 前端 (React):
echo      - 地址: http://localhost:3000
echo      - 预测页: http://localhost:3000/predict
echo.
echo   注意: 服务已在新的控制台窗口中启动
echo   要停止服务，请关闭对应的窗口
echo.

timeout /t 2 /nobreak >nul
start http://localhost:3000

echo.
pause