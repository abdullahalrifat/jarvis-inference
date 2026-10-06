#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
TARGET="${1:-main}"
STATE="$ROOT/.upgrade-state"
git diff --quiet && git diff --cached --quiet || { echo "Working tree must be clean." >&2; exit 1; }
PREVIOUS="$(git rev-parse HEAD)"
echo "$PREVIOUS" > "$STATE"
bash scripts/backup.sh
bash scripts/config-doctor.sh
git fetch --tags origin "$TARGET"
git checkout --detach "$TARGET"
if ! bash scripts/config-doctor.sh; then
  git checkout --detach "$PREVIOUS"
  exit 1
fi
if ! docker compose -f docker/docker-compose.yml build --pull jarvis-inference; then
  echo "Build failed; rolling back."
  git checkout --detach "$PREVIOUS"
  docker compose -f docker/docker-compose.yml build jarvis-inference
  docker compose -f docker/docker-compose.yml up -d ollama jarvis-inference
  exit 1
fi
docker compose -f docker/docker-compose.yml up -d ollama jarvis-inference
if ! bash scripts/wait-ready.sh; then
  echo "Readiness failed; automatic rollback to $PREVIOUS."
  git checkout --detach "$PREVIOUS"
  docker compose -f docker/docker-compose.yml build jarvis-inference
  docker compose -f docker/docker-compose.yml up -d ollama jarvis-inference
  bash scripts/wait-ready.sh || true
  exit 1
fi
if ! bash scripts/verify-models.sh; then
  echo "Model verification failed; automatic rollback to $PREVIOUS."
  git checkout --detach "$PREVIOUS"
  docker compose -f docker/docker-compose.yml build jarvis-inference
  docker compose -f docker/docker-compose.yml up -d ollama jarvis-inference
  exit 1
fi
if ! bash scripts/smoke-test.sh; then
  echo "Smoke test failed; automatic rollback to $PREVIOUS."
  git checkout --detach "$PREVIOUS"
  docker compose -f docker/docker-compose.yml build jarvis-inference
  docker compose -f docker/docker-compose.yml up -d ollama jarvis-inference
  bash scripts/wait-ready.sh || true
  exit 1
fi
rm -f "$STATE"
echo "Upgrade succeeded: $PREVIOUS -> $(git rev-parse HEAD)"
