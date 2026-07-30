#!/bin/bash
# Start AISci backend with project venv (must run from repo)
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/backend"
if [ ! -x "$ROOT/venv/bin/python" ]; then
  echo "[ERROR] venv missing. Run scripts/setup_backend.sh"
  exit 1
fi
exec "$ROOT/venv/bin/python" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
