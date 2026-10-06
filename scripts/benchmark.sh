#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
MODEL="\${1:-qwen3:1.7b}"
PORT="$(grep '^INFERENCE_PORT=' .env 2>/dev/null | cut -d= -f2- || echo 8080)"
KEY="$(grep '^INFERENCE_API_KEY=' .env 2>/dev/null | cut -d= -f2- || true)"
mkdir -p benchmarks
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
SAFE_MODEL="$(printf '%s' "$MODEL" | tr '/:' '__')"
OUT="benchmarks/\${SAFE_MODEL}-\${STAMP}.json"
python3 scripts/benchmark.py "$MODEL" --base-url "http://127.0.0.1:$PORT" --api-key "$KEY" > "$OUT"
echo "Benchmark saved to $OUT"
cat "$OUT"
