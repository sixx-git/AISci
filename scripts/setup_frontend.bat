@echo off
REM ============================================================================
REM AI Scientist - 前端设置脚本 (Windows)
REM ============================================================================

setlocal enabledelayedexpansion

echo =============================================
echo   AI Scientist - 前端设置
echo =============================================
echo.

set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."
cd /d "%PROJECT_ROOT%\frontend"

echo [1/4] 检查 Node.js 版本...
node --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到 Node.js，请先安装 Node.js 18+
    echo 下载地址: https://nodejs.org/
    exit /b 1
)
for /f "tokens=*" %%i in ('node --version') do set NODE_VERSION=%%i
echo   Node.js 版本: %NODE_VERSION%

where pnpm >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到 pnpm。可执行: npm install -g pnpm
    exit /b 1
)
for /f "tokens=*" %%i in ('pnpm --version') do set PNPM_VERSION=%%i
echo   pnpm 版本: %PNPM_VERSION%
echo.

echo [2/4] 检查 package.json...
if not exist "package.json" (
    echo 错误: 未找到 package.json 文件
    exit /b 1
)
echo   package.json 已存在
echo.

echo [3/4] 安装 pnpm 依赖...
call pnpm install
if errorlevel 1 (
    echo 错误: pnpm install 失败
    exit /b 1
)
echo   依赖安装完成
echo.

echo [4/4] 检查开发环境...
echo   前端准备就绪
echo.

echo =============================================
echo   前端设置完成!
echo =============================================
echo.
echo   下一步:
echo   1. 确保后端已启动 ^(http://localhost:8000^)
echo   2. 运行: "AI Scientist启动项目.bat" 或 scripts\run_dev.bat
echo   3. 或仅前端: cd frontend ^&^& pnpm dev
echo.
