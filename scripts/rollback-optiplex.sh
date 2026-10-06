#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
STATE="$ROOT/.upgrade-state"
TARGET="${1:-}"
if [[ -z "$TARGET" && -f "$STATE" ]]; then TARGET="$(cat "$STATE")"; fi
[[ -n "$TARGET" ]] || { echo "Usage: $0 <git-sha>" >&2; exit 2; }
git diff --quiet && git diff --cached --quiet || { echo "Working tree must be clean." >&2; exit 1; }
git checkout --detach "$TARGET"
bash scripts/config-doctor.sh
docker compose -f docker/docker-compose.yml build jarvis-inference
docker compose -f docker/docker-compose.yml up -d ollama jarvis-inference
bash scripts/wait-ready.sh
bash scripts/verify-models.sh
bash scripts/smoke-test.sh
rm -f "$STATE"
echo "Rollback complete: $(git rev-parse HEAD)"
