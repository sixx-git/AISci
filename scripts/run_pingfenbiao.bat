@echo off
REM Start pingfenbiao web service on port 8765
REM Uses AISci storage\pingfenbiao_jobs so history is shared with Full Launch

set "ROOT=%~dp0.."
cd /d "%ROOT%"
set "ROOT=%CD%"
set "PINGFEN_WEB=%ROOT%\pingfenbiao-main\pingfenbiao-main\web"
set "PINGFENBIAO_WORK_DIR=%ROOT%\storage\pingfenbiao_jobs"
set "VENV_PY=%ROOT%\venv\Scripts\python.exe"

if not exist "%PINGFEN_WEB%\app.py" (
  echo [ERROR] pingfenbiao web/app.py not found
  pause
  exit /b 1
)

if not exist "%VENV_PY%" (
  echo [ERROR] Project venv not found: %VENV_PY%
  echo         Run scripts\setup_backend.bat first
  pause
  exit /b 1
)

if not exist "%PINGFENBIAO_WORK_DIR%" mkdir "%PINGFENBIAO_WORK_DIR%"
if exist "D:\Workplace\pingfenbiao\web\_jobs" (
  robocopy "D:\Workplace\pingfenbiao\web\_jobs" "%PINGFENBIAO_WORK_DIR%" /E /XO /NFL /NDL /NJH /NJS /nc /ns /np >nul 2>&1
)
if exist "%PINGFEN_WEB%\_jobs" (
  robocopy "%PINGFEN_WEB%\_jobs" "%PINGFENBIAO_WORK_DIR%" /E /XO /NFL /NDL /NJH /NJS /nc /ns /np >nul 2>&1
)

if not defined DASHSCOPE_API_KEY (
  if exist "%ROOT%\pingfenbiao-main\pingfenbiao-main\.env" (
    echo [INFO] Using pingfenbiao .env if present
  ) else (
    echo [WARN] DASHSCOPE_API_KEY is not set. You can enter it on the Predict page.
  )
)

echo Job dir: %PINGFENBIAO_WORK_DIR%
echo Starting pingfenbiao on http://127.0.0.1:8765 ...
cd /d "%PINGFEN_WEB%"
set PINGFENBIAO_WORK_DIR=%PINGFENBIAO_WORK_DIR%
"%VENV_PY%" -m uvicorn app:app --host 127.0.0.1 --port 8765
pause
