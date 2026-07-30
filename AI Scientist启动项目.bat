@echo off
REM ============================================================================
REM AI Scientist - Launcher
REM ============================================================================

cd /d "%~dp0"

cls
echo.
echo =============================================
echo     AI Scientist - Zhi Yan Fang Zhou
echo =============================================
echo.
echo     Federal Semantic-Enhanced Multimodal AI
echo     Research Full-Process Automation Platform
echo.
echo =============================================
echo     Select Launch Mode:
echo =============================================
echo.
echo     1. Quick Start ^(Backend + Frontend^)
echo     2. Full Start ^(Backend + Frontend + Predict/Pingfenbiao^)
echo     3. Full Start + Tunnel ^(with Cloudflare^)
echo.
echo =============================================
echo     First time? Run scripts\setup_backend.bat
echo               then scripts\setup_frontend.bat
echo =============================================
set /p "choice=Enter option [1/2/3]: "

if "%choice%"=="1" (
    echo.
    echo Starting Quick Mode...
    call "%~dp0scripts\launch_stack.bat" quick
) else if "%choice%"=="2" (
    echo.
    echo Starting Full Mode...
    call "%~dp0scripts\launch_stack.bat" full
) else if "%choice%"=="3" (
    echo.
    echo Starting Full Mode with Tunnel...
    call "%~dp0scripts\launch_stack.bat" full-tunnel
) else (
    echo.
    echo Invalid option, please run again
    pause
    exit /b 1
)

if errorlevel 1 (
    echo.
    echo Launch failed. See messages above / service windows.
)
echo.
pause
