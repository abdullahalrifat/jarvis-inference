#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
MIN_FREE_GIB="\${MIN_FREE_GIB:-10}"
MIN_RAM_GIB="\${MIN_RAM_GIB:-1}"
PORT="$(grep '^INFERENCE_PORT=' .env 2>/dev/null | cut -d= -f2- || echo 8080)"
FAIL=0
disk="$(df -Pk "$ROOT" | awk 'NR==2 {print $4/1024/1024}')"
ram="$(awk '/MemAvailable:/ {print $2/1024/1024}' /proc/meminfo)"
awk -v a="$disk" -v b="$MIN_FREE_GIB" 'BEGIN {exit !(a>=b)}' || { echo "ALERT disk \${disk} GiB"; FAIL=1; }
awk -v a="$ram" -v b="$MIN_RAM_GIB" 'BEGIN {exit !(a>=b)}' || { echo "ALERT RAM \${ram} GiB"; FAIL=1; }
if ! docker compose -f docker/docker-compose.yml ps --status running ollama jarvis-inference >/dev/null 2>&1; then
  echo "ALERT one or more inference services are not running"
  FAIL=1
fi
if ! curl --fail --silent --show-error "http://127.0.0.1:\${PORT}/ready" >/dev/null; then
  echo "ALERT inference readiness failed"
  FAIL=1
fi
if (( FAIL )); then
  docker compose -f docker/docker-compose.yml ps
  exit 1
fi
echo "watchdog: healthy (disk=\${disk}GiB ram=\${ram}GiB)"
