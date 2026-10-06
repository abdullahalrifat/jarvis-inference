#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
docker compose -f docker/docker-compose.yml ps
echo
docker compose -f docker/docker-compose.yml exec -T ollama ollama ps || true
echo
./scripts/smoke-test.sh
