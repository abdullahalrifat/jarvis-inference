#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PORT="$(grep '^INFERENCE_PORT=' .env 2>/dev/null | cut -d= -f2- || echo 8080)"
for _ in {1..60}; do
  if curl --fail --silent --show-error "http://127.0.0.1:\${PORT}/ready" >/dev/null; then
    echo "Inference gateway is ready."
    exit 0
  fi
  sleep 2
done
echo "Inference gateway did not become ready." >&2
docker compose -f docker/docker-compose.yml ps
exit 1
