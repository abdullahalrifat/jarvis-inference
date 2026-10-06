#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
COMPOSE=(docker compose -f docker/docker-compose.yml)
FAIL=0
ok(){ echo "OK   $1"; }
warn(){ echo "WARN $1"; }
fail(){ echo "FAIL $1"; FAIL=1; }
command -v docker >/dev/null && ok "docker installed" || fail "docker is not installed"
docker compose version >/dev/null 2>&1 && ok "Docker Compose v2" || fail "Docker Compose v2 unavailable"
[[ -f .env ]] && ok ".env exists" || fail ".env missing; copy .env.example to .env"
[[ -f models/manifest.yaml ]] && ok "model manifest exists" || fail "models/manifest.yaml missing"
if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi
cpu="\${OLLAMA_CPUS:-2.75}"
mem="\${OLLAMA_MEMORY_LIMIT:-9g}"
queue="\${MAX_QUEUE_SIZE:-8}"
concurrency="\${MAX_CONCURRENT_REQUESTS:-1}"
loaded="\${MAX_LOADED_MODELS:-1}"
awk -v v="$cpu" 'BEGIN { exit !(v >= 2.5 && v <= 3.0) }' && ok "Ollama CPU budget $cpu" || fail "Ollama CPU budget should be 2.5-3.0"
[[ "$mem" =~ ^(8|9|10)g$ ]] && ok "Ollama memory budget $mem" || fail "Ollama memory should be 8g-10g"
[[ "$concurrency" == "1" ]] && ok "single generation" || fail "MAX_CONCURRENT_REQUESTS must be 1"
[[ "$loaded" == "1" ]] && ok "single loaded model" || fail "MAX_LOADED_MODELS must be 1"
[[ "$queue" =~ ^[1-9][0-9]*$ ]] && (( queue <= 16 )) && ok "bounded queue $queue" || fail "queue must be 1-16"
if [[ "\${INFERENCE_HOST:-127.0.0.1}" != "127.0.0.1" && -z "\${INFERENCE_API_KEY:-}" ]]; then
  fail "INFERENCE_API_KEY is required for non-loopback binding"
else
  ok "gateway exposure/auth policy"
fi
free_gib="$(awk '/MemAvailable:/ {printf "%.1f", $2/1024/1024}' /proc/meminfo 2>/dev/null || echo 0)"
disk_gib="$(df -Pk . | awk 'NR==2 {printf "%.1f", $4/1024/1024}')"
awk -v v="$free_gib" 'BEGIN { exit !(v >= 1.0) }' && ok "host available RAM \${free_gib} GiB" || warn "host available RAM is \${free_gib} GiB"
awk -v v="$disk_gib" 'BEGIN { exit !(v >= 10.0) }' && ok "free disk \${disk_gib} GiB" || fail "less than 10 GiB free disk"
"\${COMPOSE[@]}" config >/dev/null 2>&1 && ok "compose configuration" || fail "docker compose config"
if (( FAIL )); then
  echo "Configuration doctor: FAILED"
  exit 1
fi
echo "Configuration doctor: PASSED"
