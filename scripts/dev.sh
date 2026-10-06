#!/usr/bin/env bash
# Start the FinVerse dashboard: FastAPI backend on :8000, Vite frontend on :5173
# (Vite proxies /api to the backend). Ctrl+C stops both.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d web/node_modules ]; then
  (cd web && npm install)
fi

python -m uvicorn api.server:app --reload --reload-dir api --port 8000 &
BACKEND=$!
trap 'kill $BACKEND 2>/dev/null || true' EXIT INT TERM

cd web
npm run dev
