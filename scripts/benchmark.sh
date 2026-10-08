#!/usr/bin/env bash
set -euo pipefail
BASE_URL="${INFERENCE_BASE_URL:-http://127.0.0.1:8080/v1}"
KEY="${INFERENCE_API_KEY:-}"
MODEL="${MODEL:-qwen3:1.7b}"
REQUESTS="${REQUESTS:-5}"
python - "$BASE_URL" "$KEY" "$MODEL" "$REQUESTS" <<'PY'
import json,sys,time,urllib.request
base,key,model,count=sys.argv[1],sys.argv[2],sys.argv[3],int(sys.argv[4])
headers={"Content-Type":"application/json"}
if key: headers["Authorization"]=f"Bearer {key}"
times=[]
for _ in range(count):
    body=json.dumps({"model":model,"messages":[{"role":"user","content":"Return exactly: benchmark-ok"}],"max_tokens":16}).encode()
    req=urllib.request.Request(base+"/chat/completions",body,headers)
    start=time.perf_counter()
    with urllib.request.urlopen(req,timeout=120) as r: data=json.load(r)
    times.append(time.perf_counter()-start)
    assert "choices" in data
print(json.dumps({"model":model,"requests":count,"min_s":min(times),"median_s":sorted(times)[len(times)//2],"max_s":max(times)},indent=2))
PY
