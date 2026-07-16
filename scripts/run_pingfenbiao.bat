@echo off
REM Start pingfenbiao web service on port 8765
REM AISci frontend proxies /pingfenbiao to this service

cd /d "%~dp0..\pingfenbiao-main\pingfenbiao-main\web"
if not exist "app.py" (
  echo [ERROR] pingfenbiao web/app.py not found
  pause
  exit /b 1
)

if not defined DASHSCOPE_API_KEY (
  if exist "%~dp0..\pingfenbiao-main\pingfenbiao-main\web\.env" (
    echo [INFO] Using local .env if present
  ) else (
    echo [WARN] DASHSCOPE_API_KEY is not set. You can enter it on the Predict page.
  )
)

echo Starting pingfenbiao on http://127.0.0.1:8765 ...
uvicorn app:app --host 127.0.0.1 --port 8765
