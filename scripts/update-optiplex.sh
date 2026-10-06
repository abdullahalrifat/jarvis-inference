#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
git pull --ff-only
docker compose -f docker/docker-compose.yml build --pull jarvis-inference
docker compose -f docker/docker-compose.yml up -d ollama jarvis-inference
./scripts/smoke-test.sh
