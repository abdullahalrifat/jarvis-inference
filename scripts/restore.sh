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
  docker volume create jarvis-inference_ollama >/dev/null
  docker run --rm -v jarvis-inference_ollama:/target -v "$SOURCE:/backup:ro" alpine:3.22 sh -c 'rm -rf /target/* /target/.[!.]* /target/..?* 2>/dev/null || true; tar -xzf /backup/ollama-volume.tar.gz -C /target'
fi
docker compose -f docker/docker-compose.yml up -d ollama jarvis-inference
bash scripts/config-doctor.sh
bash scripts/wait-ready.sh
echo "Restore complete."
