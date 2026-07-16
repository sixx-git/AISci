@echo off
REM Start AISci backend with project venv (must run from repo)
set "ROOT=%~dp0.."
cd /d "%ROOT%\backend"
if not exist "%ROOT%\venv\Scripts\python.exe" (
  echo [ERROR] venv missing. Run scripts\setup_backend.bat
  exit /b 1
)
"%ROOT%\venv\Scripts\python.exe" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
