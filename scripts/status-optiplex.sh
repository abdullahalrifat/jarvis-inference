#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
COMPOSE=(docker compose -f docker/docker-compose.yml)
PORT="$(grep '^INFERENCE_PORT=' .env 2>/dev/null | cut -d= -f2- || echo 8080)"
KEY="$(grep '^INFERENCE_API_KEY=' .env 2>/dev/null | cut -d= -f2- || true)"
"${COMPOSE[@]}" ps
echo
echo "== Models =="
"${COMPOSE[@]}" exec -T ollama ollama list
echo
echo "== Inference status =="
if [[ -n "$KEY" ]]; then
  curl --fail --silent --show-error -H "Authorization: Bearer $KEY" "http://127.0.0.1:${PORT}/v1/inference/status" | python -m json.tool
else
  curl --fail --silent --show-error "http://127.0.0.1:${PORT}/v1/inference/status" | python -m json.tool
fi
