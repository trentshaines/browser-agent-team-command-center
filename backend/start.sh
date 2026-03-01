#!/bin/sh
set -e
echo "[start] Running migrations..."
alembic upgrade head
echo "[start] Starting uvicorn on port ${PORT:-8000}..."
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
