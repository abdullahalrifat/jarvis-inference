#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE=(docker compose -f docker/docker-compose.yml)
MODELS="${*:-}"

if ! command -v docker >/dev/null; then
  echo "Docker is required." >&2
  exit 1
fi
"${COMPOSE[@]}" version >/dev/null

if [[ -z "$MODELS" ]]; then
  if [[ ! -f .env ]]; then
    echo "No .env found. Copy .env.example to .env first." >&2
    exit 1
  fi
  MODELS="$(grep '^OLLAMA_MODELS=' .env | cut -d= -f2- | tr ',' ' ')"
fi

if [[ -z "$MODELS" ]]; then
  echo "No models configured. Set OLLAMA_MODELS or pass model names." >&2
  exit 1
fi

"${COMPOSE[@]}" up -d ollama

for _ in {1..60}; do
  if "${COMPOSE[@]}" exec -T ollama ollama list >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

for model in $MODELS; do
  echo "==> Pulling $model"
  "${COMPOSE[@]}" exec -T ollama ollama pull "$model"
  echo "==> Verifying $model"
  "${COMPOSE[@]}" exec -T ollama ollama show "$model" >/dev/null
  echo "    OK: $model"
done

echo
echo "Installed models:"
"${COMPOSE[@]}" exec -T ollama ollama list
