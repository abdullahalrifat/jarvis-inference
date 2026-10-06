#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PORT="$(grep '^INFERENCE_PORT=' .env 2>/dev/null | cut -d= -f2- || echo 8080)"
KEY="$(grep '^INFERENCE_API_KEY=' .env 2>/dev/null | cut -d= -f2- || true)"
MODEL="$1"
MODEL="${MODEL:-qwen3:1.7b}"
echo "Benchmarking $MODEL"
ARGS=(-H "Content-Type: application/json")
if [[ -n "$KEY" ]]; then ARGS+=(-H "Authorization: Bearer $KEY"); fi
curl --fail --silent --show-error "${ARGS[@]}"   "http://127.0.0.1:$PORT/v1/chat/completions"   -d "{"model":"$MODEL","messages":[{"role":"user","content":"Reply with exactly: benchmark-ok"}],"max_tokens":16}"   | python3 -m json.tool
