@echo off
REM ============================================================================
REM AI Scientist - 后端设置脚本 (Windows)
REM ============================================================================

setlocal enabledelayedexpansion

echo =============================================
echo   AI Scientist - 后端设置
echo =============================================
echo.

REM 获取项目根目录
set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."
cd /d "%PROJECT_ROOT%"
set "PROJECT_ROOT=%CD%"

REM 1. 检查 Python
echo [1/6] 检查 Python 版本...
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到 Python，请先安装 Python 3.10 / 3.11 / 3.12（推荐）
    exit /b 1
)
for /f "tokens=2" %%i in ('python --version') do set PYTHON_VERSION=%%i
echo   Python 版本: %PYTHON_VERSION%
echo.

REM 2. 创建虚拟环境（项目根目录 venv，与 launch_stack / start_backend 一致）
echo [2/6] 创建 Python 虚拟环境...
if not exist "venv" (
    python -m venv venv
    echo   虚拟环境创建成功
) else (
    echo   虚拟环境已存在
)
echo.

REM 3. 激活虚拟环境
echo [3/6] 激活虚拟环境...
call venv\Scripts\activate.bat
echo   虚拟环境已激活
echo.

REM 4. 升级 pip
echo [4/6] 升级 pip...
python -m pip install --upgrade pip
echo.

REM 5. 安装依赖（权威清单在 backend\requirements.txt）
echo [5/6] 安装 Python 依赖...
if not exist "%PROJECT_ROOT%\backend\requirements.txt" (
    echo 错误: 未找到 backend\requirements.txt
    exit /b 1
)
pip install -r "%PROJECT_ROOT%\backend\requirements.txt"
if errorlevel 1 (
    echo 错误: 依赖安装失败
    exit /b 1
)
echo.

REM 6. 创建必要的目录
echo [6/6] 创建必要的目录...
if not exist "data" mkdir data
if not exist "backend\data" mkdir backend\data
if not exist "storage" mkdir storage
if not exist "storage\documents" mkdir storage\documents
if not exist "storage\pingfenbiao_jobs" mkdir storage\pingfenbiao_jobs
if not exist "logs" mkdir logs
echo.

REM 环境文件：后端优先读 backend\.env；兼容根目录 .env
echo =============================================
if not exist "backend\.env" (
    if exist ".env" (
        echo   正在复制根目录 .env -^> backend\.env ...
        copy ".env" "backend\.env" >nul
    ) else if exist ".env.example" (
        echo   正在从 .env.example 创建 backend\.env ...
        copy ".env.example" "backend\.env" >nul
        if not exist ".env" copy ".env.example" ".env" >nul
        echo.
        echo   请编辑 backend\.env 并填入 QWEN_API_KEY（或设 USE_MOCK_LLM=true）
    ) else (
        echo   警告: 未找到 .env.example，请手动创建 backend\.env
    )
) else (
    echo   backend\.env 已存在（后端实际读取此文件）
)
echo.

echo =============================================
echo   后端设置完成!
echo =============================================
echo.
echo   下一步:
echo   1. 编辑 backend\.env（填入 QWEN_API_KEY；默认 SQLite，无需 MySQL）
echo   2. 可选: python scripts\init_db.py
echo   3. 启动: "AI Scientist启动项目.bat" 或 scripts\run_dev.bat
echo.
echo   激活虚拟环境: venv\Scripts\activate
echo.
