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

REM 1. 检查 Python
echo [1/6] 检查 Python 版本...
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到 Python，请先安装 Python 3.9+
    exit /b 1
)
for /f "tokens=2" %%i in ('python --version') do set PYTHON_VERSION=%%i
echo   Python 版本: %PYTHON_VERSION%
echo.

REM 2. 创建虚拟环境
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

REM 5. 安装依赖
echo [5/6] 安装 Python 依赖...
pip install -r requirements.txt
echo.

REM 6. 创建必要的目录
echo [6/6] 创建必要的目录...
if not exist "data" mkdir data
if not exist "storage" mkdir storage
if not exist "storage\documents" mkdir storage\documents
if not exist "logs" mkdir logs
echo.

REM 检查 .env 文件
echo =============================================
if not exist ".env" (
    echo   提示: .env 文件不存在，正在从 .env.example 复制...
    copy .env.example .env >nul
    echo.
    echo   ⚠️  重要: 请编辑 .env 文件并填入你的配置!
    echo   特别是 QWEN_API_KEY 和 DATABASE_URL
) else (
    echo   ✅ .env 文件已存在
)
echo.

echo =============================================
echo   后端设置完成!
echo =============================================
echo.
echo   下一步操作:
echo   1. 编辑 .env 文件配置你的设置
echo   2. 确保 MySQL 数据库已创建
echo   3. 运行: python scripts\init_db.py
echo   4. 运行: scripts\run_dev.bat
echo.
echo   要激活虚拟环境: venv\Scripts\activate
echo.
