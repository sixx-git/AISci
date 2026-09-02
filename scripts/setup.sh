#!/bin/sh
# Meoo remote build: install deps + build frontend SPA + pingfenbiao
set -eu
cd /code

echo "[setup] Python deps (requirements.meoo.txt)..."
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.meoo.txt

if [ -f /code/pingfenbiao-main/pingfenbiao-main/web/requirements.txt ]; then
  echo "[setup] pingfenbiao web deps..."
  python -m pip install -r /code/pingfenbiao-main/pingfenbiao-main/web/requirements.txt
fi

echo "[setup] Frontend deps + build..."
cd /code/frontend
corepack enable || true
pnpm install --frozen-lockfile || pnpm install
# Same-origin API in production (empty VITE_API_BASE_URL → /api/v1)
VITE_API_BASE_URL= pnpm build
cd /code

mkdir -p /code/backend/data /code/backend/storage /code/backend/storage/pingfenbiao_jobs /code/logs
echo "[setup] Done."
