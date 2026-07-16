@echo off
REM ============================================================================
REM AI Scientist - Full Environment (Backend + Frontend + Pingfenbiao)
REM ============================================================================
cd /d "%~dp0"
call "%~dp0..\scripts\launch_stack.bat" full
if errorlevel 1 (
    echo.
    pause
    exit /b 1
)
echo.
pause
