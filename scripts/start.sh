#!/bin/sh
# Meoo runtime: AISci (:$PORT) + pingfenbiao (:8765)
# Do NOT shell-source .env (values may contain spaces). App loads backend/.env via pydantic.
set -eu
cd /code

PORT="${PORT:-9000}"
export BACKEND_HOST=0.0.0.0
export BACKEND_PORT="$PORT"
export DEBUG="${DEBUG:-false}"

# Prefer Meoo Postgres direct URL when platform injects it
if [ -n "${SUPABASE_DB_URL:-}" ]; then
  case "$SUPABASE_DB_URL" in
    postgres://*)
      export DATABASE_URL="postgresql+psycopg2://${SUPABASE_DB_URL#postgres://}"
      ;;
    postgresql://*)
      export DATABASE_URL="postgresql+psycopg2://${SUPABASE_DB_URL#postgresql://}"
      ;;
    *)
      export DATABASE_URL="$SUPABASE_DB_URL"
      ;;
  esac
fi

# Defaults if not already in environment / .env
export QWEN_MODEL="${QWEN_MODEL:-qwen3.6-plus}"
export QWEN_VL_MODEL="${QWEN_VL_MODEL:-qwen3.6-plus}"
export EMBEDDING_BACKEND="${EMBEDDING_BACKEND:-qwen}"
export EMBEDDING_MODEL="${EMBEDDING_MODEL:-text-embedding-v3}"
export CORS_ORIGINS="${CORS_ORIGINS:-*}"
export AISCI_CLOUD_DB_SYNC="${AISCI_CLOUD_DB_SYNC:-true}"
export AISCI_CLOUD_DB_SYNC_INTERVAL_SEC="${AISCI_CLOUD_DB_SYNC_INTERVAL_SEC:-10800}"

# pingfenbiao (scoring service)
export PINGFENBIAO_URL="${PINGFENBIAO_URL:-http://127.0.0.1:8765}"
export PINGFENBIAO_WORK_DIR="${PINGFENBIAO_WORK_DIR:-/code/backend/storage/pingfenbiao_jobs}"
if [ -z "${DASHSCOPE_API_KEY:-}" ] && [ -n "${QWEN_API_KEY:-}" ]; then
  export DASHSCOPE_API_KEY="$QWEN_API_KEY"
fi

mkdir -p /code/backend/data /code/backend/storage /code/backend/storage/iterative_experiments "$PINGFENBIAO_WORK_DIR" /code/logs /code/shaxiang-main/shaxiang-main/data/charts/smoke

PINGFEN_WEB="/code/pingfenbiao-main/pingfenbiao-main/web"
if [ -f "$PINGFEN_WEB/app.py" ]; then
  echo "[start] pingfenbiao on 127.0.0.1:8765"
  (
    cd "$PINGFEN_WEB"
    exec python -m uvicorn app:app --host 127.0.0.1 --port 8765
  ) &
  sleep 2
else
  echo "[start] WARN: pingfenbiao web not found, skip"
fi

echo "[start] AISci on 0.0.0.0:${PORT}"
cd /code/backend
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
