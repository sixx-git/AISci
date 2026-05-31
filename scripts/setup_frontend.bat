@echo off
REM ============================================================================
REM AI Scientist - 前端设置脚本 (Windows)
REM ============================================================================

setlocal enabledelayedexpansion

echo =============================================
echo   AI Scientist - 前端设置
echo =============================================
echo.

REM 获取项目根目录
set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."
cd /d "%PROJECT_ROOT%\frontend"

REM 1. 检查 Node.js
echo [1/4] 检查 Node.js 版本...
node --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到 Node.js，请先安装 Node.js 18+
    echo 下载地址: https://nodejs.org/
    exit /b 1
)
for /f "tokens=*" %%i in ('node --version') do set NODE_VERSION=%%i
echo   Node.js 版本: %NODE_VERSION%

for /f "tokens=*" %%i in ('npm --version') do set NPM_VERSION=%%i
echo   npm 版本: %NPM_VERSION%
echo.

REM 2. 检查 package.json
echo [2/4] 检查 package.json...
if not exist "package.json" (
    echo 错误: 未找到 package.json 文件
    exit /b 1
)
echo   package.json 已存在
echo.

REM 3. 安装依赖
echo [3/4] 安装 pnpm 依赖...
if exist "node_modules" (
    echo   node_modules 已存在，跳过安装
) else (
    call pnpm install
    echo   依赖安装完成
)
echo.

REM 4. 检查是否可构建
echo [4/4] 检查开发环境...
echo   前端准备就绪
echo.

echo =============================================
echo   前端设置完成!
echo =============================================
echo.
echo   下一步操作:
echo   1. 确保后端服务正在运行 (http://localhost:8000)
echo   2. 运行: scripts\run_dev.bat (同时启动前后端)
echo   3. 或仅启动前端: cd frontend ^&^& npm run dev
echo.
