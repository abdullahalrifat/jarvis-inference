#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
COMPOSE=(docker compose -f docker/docker-compose.yml)
BACKUP_DIR="${BACKUP_DIR:-$HOME/jarvis-inference-backups}"
BACKUP_MODELS="${BACKUP_MODELS:-0}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$BACKUP_DIR/$STAMP"
mkdir -p "$OUT"
chmod 700 "$BACKUP_DIR" "$OUT"
tar -czf "$OUT/config.tar.gz" .env .env.example docker/docker-compose.yml docker/Dockerfile models/manifest.yaml pyproject.toml requirements.txt 2>/dev/null || true
git rev-parse HEAD > "$OUT/git-revision.txt"
docker compose -f docker/docker-compose.yml config > "$OUT/compose-rendered.yml"
sha256sum "$OUT/config.tar.gz" "$OUT/compose-rendered.yml" > "$OUT/SHA256SUMS"
if [[ "$BACKUP_MODELS" == "1" ]]; then
  echo "Stopping Ollama for a consistent model-volume backup..."
  docker compose -f docker/docker-compose.yml stop ollama
  CID="$(${COMPOSE[@]} ps -q ollama)"
  docker exec "$CID" tar -czf /tmp/ollama-volume.tar.gz -C /root/.ollama .
  docker cp "$CID:/tmp/ollama-volume.tar.gz" "$OUT/ollama-volume.tar.gz"
  docker exec "$CID" rm -f /tmp/ollama-volume.tar.gz
  docker compose -f docker/docker-compose.yml start ollama
  sha256sum "$OUT/ollama-volume.tar.gz" >> "$OUT/SHA256SUMS"
fi
ln -sfn "$OUT" "$BACKUP_DIR/latest"
echo "Backup created: $OUT"
