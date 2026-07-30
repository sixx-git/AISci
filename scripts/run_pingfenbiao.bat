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
REM 仅在目标目录为空时做一次迁移，避免每次启动把已删除的任务从旧 _jobs 拷回来
set "HAS_JOBS="
for /f %%i in ('dir /b /ad "%PINGFENBIAO_WORK_DIR%" 2^>nul') do set "HAS_JOBS=1"
if not defined HAS_JOBS (
  if exist "D:\Workplace\pingfenbiao\web\_jobs" (
    echo [INFO] Migrating jobs from D:\Workplace\pingfenbiao\web\_jobs ...
    robocopy "D:\Workplace\pingfenbiao\web\_jobs" "%PINGFENBIAO_WORK_DIR%" /E /XO /NFL /NDL /NJH /NJS /nc /ns /np >nul 2>&1
  )
  if exist "%PINGFEN_WEB%\_jobs" (
    echo [INFO] Migrating jobs from %PINGFEN_WEB%\_jobs ...
    robocopy "%PINGFEN_WEB%\_jobs" "%PINGFENBIAO_WORK_DIR%" /E /XO /NFL /NDL /NJH /NJS /nc /ns /np >nul 2>&1
  )
)

if not defined DASHSCOPE_API_KEY (
  REM 优先 backend\.env（与 uvicorn 实际读取一致），再回退根目录 .env
  if exist "%ROOT%\backend\.env" (
    for /f "usebackq tokens=1,* delims==" %%A in (`findstr /b /c:"QWEN_API_KEY=" "%ROOT%\backend\.env"`) do (
      if not defined DASHSCOPE_API_KEY set "DASHSCOPE_API_KEY=%%B"
    )
  )
)
if not defined DASHSCOPE_API_KEY (
  if exist "%ROOT%\.env" (
    for /f "usebackq tokens=1,* delims==" %%A in (`findstr /b /c:"QWEN_API_KEY=" "%ROOT%\.env"`) do (
      if not defined DASHSCOPE_API_KEY set "DASHSCOPE_API_KEY=%%B"
    )
  )
)
if not defined DASHSCOPE_API_KEY (
  if exist "%ROOT%\pingfenbiao-main\pingfenbiao-main\.env" (
    for /f "usebackq tokens=1,* delims==" %%A in (`findstr /b /c:"DASHSCOPE_API_KEY=" "%ROOT%\pingfenbiao-main\pingfenbiao-main\.env"`) do (
      if not defined DASHSCOPE_API_KEY set "DASHSCOPE_API_KEY=%%B"
    )
  )
)
if defined DASHSCOPE_API_KEY (
  echo [INFO] DashScope API Key loaded for pingfenbiao
) else (
  echo [WARN] DASHSCOPE_API_KEY / QWEN_API_KEY not found. Enter key on Predict page if needed.
)

echo Job dir: %PINGFENBIAO_WORK_DIR%
echo Starting pingfenbiao on http://127.0.0.1:8765 ...
cd /d "%PINGFEN_WEB%"
set PINGFENBIAO_WORK_DIR=%PINGFENBIAO_WORK_DIR%
"%VENV_PY%" -m uvicorn app:app --host 127.0.0.1 --port 8765
pause
