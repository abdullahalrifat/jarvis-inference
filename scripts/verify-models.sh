#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
COMPOSE=(docker compose -f docker/docker-compose.yml)
MANIFEST="$ROOT/models/manifest.yaml"
ALLOW_UNPINNED=0
for arg in "$@"; do
  case "$arg" in
    --allow-unpinned) ALLOW_UNPINNED=1 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done
command -v docker >/dev/null || { echo "Docker is required." >&2; exit 1; }
[[ -f "$MANIFEST" ]] || { echo "Missing $MANIFEST" >&2; exit 1; }
"\${COMPOSE[@]}" exec -T ollama ollama list >/dev/null
python3 - "$MANIFEST" "$ALLOW_UNPINNED" <<'PY'
import json
import subprocess
import sys

manifest_path, allow_unpinned = sys.argv[1], bool(int(sys.argv[2]))
models = []
current = None
for raw in open(manifest_path, encoding="utf-8"):
    line = raw.strip()
    if line.startswith("- name:"):
        current = {"name": line.split(":", 1)[1].strip()}
        models.append(current)
    elif current and line.startswith("digest:"):
        current["digest"] = line.split(":", 1)[1].strip().strip('"')
data = json.loads(subprocess.check_output(
    ["docker", "compose", "-f", "docker/docker-compose.yml", "exec", "-T",
     "jarvis-inference", "python", "-c", "import urllib.request; print(urllib.request.urlopen(\"http://ollama:11434/api/tags\").read().decode())"], text=True
))
installed = {m.get("name"): m.get("digest", "") for m in data.get("models", [])}
failed = False
for model in models:
    name, expected = model["name"], model.get("digest", "")
    actual = installed.get(name)
    if not actual:
        print(f"FAIL {name}: not installed")
        failed = True
    elif not expected:
        print(f"UNPINNED {name}: installed digest {actual}")
        if not allow_unpinned:
            failed = True
    elif actual != expected:
        print(f"FAIL {name}: digest mismatch expected={expected} actual={actual}")
        failed = True
    else:
        print(f"OK   {name}: {actual}")
if failed:
    raise SystemExit(1)
PY
