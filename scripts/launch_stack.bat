@echo off
REM ============================================================================
REM AI Scientist - Unified stack launcher
REM Usage: launch_stack.bat [quick|full|full-tunnel]
REM   quick       = Backend + Frontend
REM   full        = Backend + Frontend + Pingfenbiao (default for run_full)
REM   full-tunnel = full + Cloudflare Tunnel
REM ============================================================================

setlocal enabledelayedexpansion

set "MODE=%~1"
if "%MODE%"=="" set "MODE=quick"

set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."
cd /d "%PROJECT_ROOT%"
set "PROJECT_ROOT=%CD%"
set "VENV_PY=%PROJECT_ROOT%\venv\Scripts\python.exe"
set "VENV_ACTIVATE=%PROJECT_ROOT%\venv\Scripts\activate.bat"
set "PINGFEN_WEB=%PROJECT_ROOT%\pingfenbiao-main\pingfenbiao-main\web"
set "PINGFENBIAO_WORK_DIR=%PROJECT_ROOT%\storage\pingfenbiao_jobs"

echo =============================================
echo   AI Scientist - Launch [%MODE%]
echo =============================================
echo   Root: %PROJECT_ROOT%
echo.

if not exist "%VENV_PY%" (
    echo [ERROR] venv not found: %VENV_PY%
    echo         Run: scripts\setup_backend.bat
    exit /b 1
)

REM Backend 实际读取 backend\.env（优先于根目录 .env）。改密钥请改 backend\.env。
if not exist "%PROJECT_ROOT%\backend\.env" (
    if exist "%PROJECT_ROOT%\.env" (
        echo [INFO] backend\.env missing, copying from project root .env ...
        copy "%PROJECT_ROOT%\.env" "%PROJECT_ROOT%\backend\.env" >nul
        echo.
    ) else if exist "%PROJECT_ROOT%\.env.example" (
        echo [WARN] backend\.env missing, copying from .env.example ...
        copy "%PROJECT_ROOT%\.env.example" "%PROJECT_ROOT%\backend\.env" >nul
        echo         Please edit backend\.env then re-run if needed.
        echo.
    ) else (
        echo [WARN] No .env found. Backend may fail without QWEN_API_KEY / USE_MOCK_LLM.
        echo.
    )
) else if exist "%PROJECT_ROOT%\.env" (
    echo [INFO] Using backend\.env for QWEN_API_KEY ^(root .env is ignored when backend\.env exists^).
    echo.
)

if not exist "%PROJECT_ROOT%\data" mkdir "%PROJECT_ROOT%\data"
if not exist "%PROJECT_ROOT%\storage" mkdir "%PROJECT_ROOT%\storage"
if not exist "%PROJECT_ROOT%\storage\documents" mkdir "%PROJECT_ROOT%\storage\documents"
if not exist "%PROJECT_ROOT%\storage\pingfenbiao_jobs" mkdir "%PROJECT_ROOT%\storage\pingfenbiao_jobs"
if not exist "%PROJECT_ROOT%\logs" mkdir "%PROJECT_ROOT%\logs"

REM 仅当统一目录尚无任务时做一次迁移，避免每次启动把已删除记录从旧 _jobs 拷回
set "HAS_JOBS="
for /f %%i in ('dir /b /ad "%PINGFENBIAO_WORK_DIR%" 2^>nul') do set "HAS_JOBS=1"
if not defined HAS_JOBS (
    if exist "%PROJECT_ROOT%\..\pingfenbiao\web\_jobs" (
        robocopy "%PROJECT_ROOT%\..\pingfenbiao\web\_jobs" "%PINGFENBIAO_WORK_DIR%" /E /XO /NFL /NDL /NJH /NJS /nc /ns /np >nul 2>&1
    )
    if exist "D:\Workplace\pingfenbiao\web\_jobs" (
        robocopy "D:\Workplace\pingfenbiao\web\_jobs" "%PINGFENBIAO_WORK_DIR%" /E /XO /NFL /NDL /NJH /NJS /nc /ns /np >nul 2>&1
    )
    if exist "%PINGFEN_WEB%\_jobs" (
        robocopy "%PINGFEN_WEB%\_jobs" "%PINGFENBIAO_WORK_DIR%" /E /XO /NFL /NDL /NJH /NJS /nc /ns /np >nul 2>&1
    )
)

REM ---- free stuck ports optionally warn ----
call :port_in_use 8000
if "!PORT_BUSY!"=="1" (
    echo [WARN] Port 8000 already in use. Reusing existing backend if healthy.
    echo         NOTE: reusing will NOT reload .env / API key changes.
    echo         To apply a new QWEN_API_KEY: close "AI Scientist Backend" window, then re-run.
    call :wait_url "http://127.0.0.1:8000/health" 5
    if errorlevel 1 (
        echo [ERROR] Port 8000 busy but /health failed. Close the old Backend window and retry.
        exit /b 1
    )
    echo [OK] Backend already healthy on :8000
    goto after_backend
)

echo =============================================
echo   Starting Backend ^(:8000^)...
echo =============================================
REM Critical: new console must use venv python explicitly (activate does NOT carry over to start cmd)
start "AI Scientist Backend" /D "%PROJECT_ROOT%\backend" cmd /k ""%VENV_PY%" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

echo Waiting for backend /health ...
call :wait_url "http://127.0.0.1:8000/health" 90
if errorlevel 1 (
    echo [ERROR] Backend did not become healthy in time.
    echo         Check the "AI Scientist Backend" window for traceback.
    exit /b 1
)
echo [OK] Backend is up

:after_backend

if /i "%MODE%"=="quick" goto start_frontend

echo =============================================
echo   Starting Pingfenbiao ^(:8765^)...
echo =============================================
if not exist "%PINGFEN_WEB%\app.py" (
    echo [WARN] pingfenbiao not found, skipping Predict service
    goto start_frontend
)

REM 占用 8765 时先确认是否读到统一历史；否则结束旧进程再拉起
call :port_in_use 8765
if "!PORT_BUSY!"=="1" (
    powershell -NoProfile -Command "try { $a = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/api/impact/history' -TimeoutSec 3; if (@($a).Count -gt 0) { exit 0 } else { exit 2 } } catch { exit 1 }" >nul 2>&1
    if not errorlevel 1 (
        echo [OK] Reusing pingfenbiao on :8765 ^(history available^)
        goto start_frontend
    )
    echo [WARN] Port 8765 busy but history empty/unreachable — restarting with shared job dir
    call :kill_port 8765
    timeout /t 2 /nobreak >nul
)

REM 必须传入 PINGFENBIAO_WORK_DIR，否则会落到空的 web\_jobs
start "Pingfenbiao Service" /D "%PINGFEN_WEB%" cmd /k "set PINGFENBIAO_WORK_DIR=%PINGFENBIAO_WORK_DIR%&& "%VENV_PY%" -m uvicorn app:app --host 127.0.0.1 --port 8765"
echo Waiting for pingfenbiao ...
call :wait_url "http://127.0.0.1:8765/api/impact/history" 45
if errorlevel 1 (
    echo [WARN] Pingfenbiao not ready yet. Predict page may fail until it finishes loading.
) else (
    echo [OK] Pingfenbiao is up ^(jobs: %PINGFENBIAO_WORK_DIR%^)
)

:start_frontend
echo =============================================
echo   Starting Frontend ^(:3000^)...
echo =============================================

call :port_in_use 3000
if "!PORT_BUSY!"=="1" (
    echo [WARN] Port 3000 already in use. Reusing existing Vite if responding.
    call :wait_url "http://127.0.0.1:3000/" 5
    if errorlevel 1 (
        echo [ERROR] Port 3000 busy but not responding. Close the old Frontend window and retry.
        exit /b 1
    )
    goto after_frontend
)

where pnpm >nul 2>&1
if errorlevel 1 (
    echo [ERROR] pnpm not found in PATH. Install pnpm or open a terminal where pnpm works.
    exit /b 1
)

start "AI Scientist Frontend" /D "%PROJECT_ROOT%\frontend" cmd /k "pnpm dev"

echo Waiting for frontend ...
call :wait_url "http://127.0.0.1:3000/" 60
if errorlevel 1 (
    echo [ERROR] Frontend did not start in time. Check the Frontend window.
    exit /b 1
)
echo [OK] Frontend is up

:after_frontend

if /i not "%MODE%"=="full-tunnel" goto summary

echo =============================================
echo   Starting Cloudflare Tunnel...
echo =============================================
set "PATH=%PATH%;C:\Program Files (x86)\cloudflared;C:\Program Files\cloudflared"
where cloudflared >nul 2>&1
if errorlevel 1 (
    echo [WARN] cloudflared not installed. Run: winget install Cloudflare.cloudflared
) else (
    start "Cloudflare Tunnel" cmd /k "cloudflared tunnel --url http://127.0.0.1:3000"
    echo [OK] Tunnel window opened — copy the https://*.trycloudflare.com URL from that window
)

:summary
echo.
echo =============================================
echo   Services ready
echo =============================================
echo   Backend:    http://localhost:8000
echo   API Docs:   http://localhost:8000/docs
echo   Frontend:   http://localhost:3000
if /i not "%MODE%"=="quick" (
    echo   Pingfenbiao: http://localhost:8765
    echo   Predict:    http://localhost:3000/predict
)
if /i "%MODE%"=="full-tunnel" (
    echo   Tunnel:     see "Cloudflare Tunnel" window
)
echo.
echo   Tip: Keep Backend/Frontend windows open. Close them to stop.
echo.

timeout /t 2 /nobreak >nul
start http://localhost:3000
exit /b 0

REM ============================================================================
REM Helpers
REM ============================================================================
:port_in_use
set "PORT_BUSY=0"
netstat -ano | findstr /R /C:":%~1 .*LISTENING" >nul 2>&1
if not errorlevel 1 set "PORT_BUSY=1"
exit /b 0

:kill_port
REM kill LISTENING pid on port %1
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%~1 .*LISTENING"') do (
    echo Killing PID %%P on port %~1
    taskkill /F /PID %%P >nul 2>&1
)
exit /b 0

:wait_url
REM %1 = URL, %2 = max seconds
set "WAIT_URL=%~1"
set /a WAIT_MAX=%~2
if "%WAIT_MAX%"=="" set /a WAIT_MAX=60
set /a WAIT_I=0
:wait_url_loop
powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri '%WAIT_URL%' -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
if not errorlevel 1 exit /b 0
set /a WAIT_I+=2
if !WAIT_I! geq !WAIT_MAX! exit /b 1
timeout /t 2 /nobreak >nul
goto wait_url_loop
