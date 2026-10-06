#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
BACKUP_DIR="${BACKUP_DIR:-$HOME/jarvis-inference-backups}"
SOURCE="${1:-$BACKUP_DIR/latest}"
RESTORE_MODELS="${RESTORE_MODELS:-0}"
[[ -d "$SOURCE" ]] || { echo "Backup not found: $SOURCE" >&2; exit 1; }
[[ -f "$SOURCE/config.tar.gz" ]] || { echo "Missing config.tar.gz" >&2; exit 1; }
if [[ -f "$SOURCE/SHA256SUMS" ]]; then
  (cd "$SOURCE" && sha256sum -c SHA256SUMS --ignore-missing)
fi
docker compose -f docker/docker-compose.yml down || true
tar -xzf "$SOURCE/config.tar.gz" -C "$ROOT"
if [[ "$RESTORE_MODELS" == "1" && -f "$SOURCE/ollama-volume.tar.gz" ]]; then
  "${COMPOSE[@]}" up -d ollama
  CID="$("${COMPOSE[@]}" ps -q ollama)"
  docker cp "$SOURCE/ollama-volume.tar.gz" "$CID:/tmp/ollama-volume.tar.gz"
  docker exec "$CID" sh -c 'rm -rf /root/.ollama/* /root/.ollama/.[!.]* /root/.ollama/..?* 2>/dev/null || true'
  docker exec "$CID" tar -xzf /tmp/ollama-volume.tar.gz -C /root/.ollama
  docker exec "$CID" rm -f /tmp/ollama-volume.tar.gz
fi
docker compose -f docker/docker-compose.yml up -d ollama jarvis-inference
bash scripts/config-doctor.sh
bash scripts/wait-ready.sh
echo "Restore complete."
