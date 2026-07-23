#!/bin/sh
set -eu

if [ -n "${REDIS_URL:-}" ]; then
  export CELERY_BROKER_URL="${CELERY_BROKER_URL:-$REDIS_URL}"
  export CELERY_RESULT_BACKEND="${CELERY_RESULT_BACKEND:-$REDIS_URL}"
fi

exec uv run celery -A app.workers.celery_app.celery_app worker \
  --loglevel=INFO \
  -Q source.health,source.discovery,article.fetch,report.render,report.deliver,matching.lexical,matching.semantic,embedding.generate,matching.rerank
