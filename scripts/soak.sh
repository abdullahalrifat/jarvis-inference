#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
DURATION_SECONDS="${DURATION_SECONDS:-3600}"
INTERVAL_SECONDS="${INTERVAL_SECONDS:-15}"
END=$(( $(date +%s) + DURATION_SECONDS ))
i=0
while (( $(date +%s) < END )); do
  curl --fail --silent http://127.0.0.1:${INFERENCE_PORT:-8080}/ready >/dev/null
  curl --fail --silent http://127.0.0.1:${INFERENCE_PORT:-8080}/health >/dev/null
  ((i+=1))
  if (( i % 20 == 0 )); then
    docker stats --no-stream --format '{{.Name}} {{.CPUPerc}} {{.MemUsage}}'
  fi
  sleep "$INTERVAL_SECONDS"
done
echo "inference soak completed: $i readiness cycles"
