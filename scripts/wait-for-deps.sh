#!/usr/bin/env bash
set -euo pipefail

HOST="${POSTGRES_HOST:-postgres}"
PORT="${POSTGRES_PORT:-5432}"
REDIS_HOST="${REDIS_HOST:-redis}"
REDIS_PORT="${REDIS_PORT:-6379}"
RETRIES="${WAIT_RETRIES:-60}"

echo "Waiting for Postgres at ${HOST}:${PORT}..."
for i in $(seq 1 "$RETRIES"); do
  if (echo >"/dev/tcp/${HOST}/${PORT}") >/dev/null 2>&1; then
    echo "Postgres is reachable."
    break
  fi
  if [[ "$i" -eq "$RETRIES" ]]; then
    echo "Postgres not reachable after ${RETRIES} attempts" >&2
    exit 1
  fi
  sleep 1
done

echo "Waiting for Redis at ${REDIS_HOST}:${REDIS_PORT}..."
for i in $(seq 1 "$RETRIES"); do
  if (echo >"/dev/tcp/${REDIS_HOST}/${REDIS_PORT}") >/dev/null 2>&1; then
    echo "Redis is reachable."
    break
  fi
  if [[ "$i" -eq "$RETRIES" ]]; then
    echo "Redis not reachable after ${RETRIES} attempts" >&2
    exit 1
  fi
  sleep 1
done

echo "Dependencies ready."
