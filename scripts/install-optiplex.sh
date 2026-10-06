#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
command -v docker >/dev/null || { echo "Docker is required."; exit 1; }
docker compose version >/dev/null || { echo "Docker Compose v2 is required."; exit 1; }
if [[ ! -f .env ]]; then cp .env.example .env; echo "Created .env. Set INFERENCE_API_KEY before remote exposure."; fi
chmod 700 scripts/*.sh
docker compose -f docker/docker-compose.yml build --pull jarvis-inference
docker compose -f docker/docker-compose.yml up -d ollama jarvis-inference
for _ in {1..60}; do
  if docker compose -f docker/docker-compose.yml exec -T ollama ollama list >/dev/null 2>&1; then break; fi
  sleep 2
done
models="$(grep '^OLLAMA_MODELS=' .env | cut -d= -f2- || true)"
for model in $models; do
  echo "Ensuring model is installed: $model"
  docker compose -f docker/docker-compose.yml exec -T ollama ollama pull "$model"
done
./scripts/smoke-test.sh
