#!/bin/sh
set -eu

PORT="${PORT:-8000}"

if [ -n "${REDIS_URL:-}" ]; then
  export CELERY_BROKER_URL="${CELERY_BROKER_URL:-$REDIS_URL}"
  export CELERY_RESULT_BACKEND="${CELERY_RESULT_BACKEND:-$REDIS_URL}"
fi

uv run alembic upgrade head
uv run python -m app.db.seed
exec uv run uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
