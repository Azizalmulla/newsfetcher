#!/bin/sh
set -eu

if [ "${SERVICE_ROLE:-api}" = "worker" ]; then
  exec /bin/sh /workspace/infra/docker/start-worker.sh
fi

exec /bin/sh /workspace/infra/docker/start-api.sh
