@echo off
REM ============================================================================
REM AI Scientist - 一键启动项目
REM ============================================================================

cd /d "%~dp0"

cls
echo.
echo =============================================
echo     AI Scientist - 智研方舟
echo =============================================
echo.
echo     联邦语义增强的多模态 AI 科研全流程自动化平台
echo.
echo =============================================
echo     请选择启动模式:
echo =============================================
echo.
echo     1. 快速启动 (后端 + 前端)
echo     2. 完整启动 (后端 + 前端 + 评分表)
echo     3. 完整启动 + 内网渗透 (含 Cloudflare Tunnel)
echo.
echo =============================================
set /p "choice=请输入选项 [1/2/3]: "

if "%choice%"=="1" (
    echo.
    echo 正在启动快速模式...
    call scripts\run_dev.bat
) else if "%choice%"=="2" (
    echo.
    echo 正在启动完整模式...
    call run_full\run_full.bat
) else if "%choice%"=="3" (
    echo.
    echo 正在启动完整模式 + 内网渗透...
    call run_full\run_full_with_tunnel.bat
) else (
    echo.
    echo ❌ 无效选项，请重新运行
    pause
    exit /b 1
)