#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
MANIFEST="$ROOT/models/manifest.yaml"
python3 - "$MANIFEST" <<'PY'
import json
import subprocess
import sys

path = sys.argv[1]
data = json.loads(subprocess.check_output(
    ["docker", "compose", "-f", "docker/docker-compose.yml", "exec", "-T",
     "jarvis-inference", "python", "-c", "import urllib.request; print(urllib.request.urlopen(\"http://ollama:11434/api/tags\").read().decode())"], text=True
))
digests = {m.get("name"): m.get("digest", "") for m in data.get("models", [])}
result = []
current = None
for raw in open(path, encoding="utf-8"):
    stripped = raw.strip()
    if stripped.startswith("- name:"):
        current = stripped.split(":", 1)[1].strip()
    if stripped.startswith("digest:") and current:
        digest = digests.get(current, "")
        raw = '    digest: "' + digest + '"\n'
    result.append(raw)
sys.stdout.write("".join(result))
PY
echo "Locked model digests in $MANIFEST"
cat "$MANIFEST"
