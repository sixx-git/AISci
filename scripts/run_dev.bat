@echo off
REM ============================================================================
REM AI Scientist - Dev launcher (Backend + Frontend)
REM ============================================================================
cd /d "%~dp0"
call "%~dp0launch_stack.bat" quick
if errorlevel 1 (
    echo.
    pause
    exit /b 1
)
echo.
pause
