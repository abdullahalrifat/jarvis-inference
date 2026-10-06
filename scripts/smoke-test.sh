#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PORT="$(grep '^INFERENCE_PORT=' .env 2>/dev/null | cut -d= -f2- || echo 8080)"
BASE="http://127.0.0.1:$PORT"
curl --fail --silent --show-error "$BASE/health" >/dev/null
curl --fail --silent --show-error "$BASE/ready" >/dev/null
echo "Health: OK"
echo "Ready: OK"
KEY="$(grep '^INFERENCE_API_KEY=' .env 2>/dev/null | cut -d= -f2- || true)"
if [[ -n "$KEY" ]]; then
  curl --fail --silent --show-error -H "Authorization: Bearer $KEY" "$BASE/v1/models" >/dev/null
  echo "Authentication: OK"
else
  echo "Authentication: disabled (localhost-only deployment)."
fi
