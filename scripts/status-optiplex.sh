#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
COMPOSE=(docker compose -f docker/docker-compose.yml)

"${COMPOSE[@]}" ps
echo
echo "== Models =="
"${COMPOSE[@]}" exec -T ollama ollama list
echo
echo "== Inference status =="
curl --fail --silent --show-error "http://127.0.0.1:${INFERENCE_PORT:-8080}/v1/inference/status" | python -m json.tool
