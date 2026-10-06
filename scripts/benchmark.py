from __future__ import annotations

import argparse
import json
import statistics
import time
from urllib.request import Request, urlopen


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = min(len(ordered) - 1, round((len(ordered) - 1) * p))
    return ordered[index]


def request(\n    base: str, model: str, token_limit: int, key: str, keep_alive: str | int | None\n) -> dict:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with exactly: benchmark-ok"}],
        "max_tokens": token_limit,
        "stream": True,
    }
    if keep_alive is not None:
        payload["keep_alive"] = keep_alive
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    started = time.perf_counter()
    req = Request(
        f"{base.rstrip('/')}/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers=headers,
        method="POST",
    )
    first_token = None
    usage: dict = {}
    with urlopen(req, timeout=900) as response:
        for raw in response:
            line = raw.decode().strip()
            if not line.startswith("data: "):
                continue
            data_text = line[6:]
            if data_text == "[DONE]":
                break
            data = json.loads(data_text)
            if first_token is None:
                first_token = time.perf_counter()
            if data.get("usage"):
                usage = data["usage"]
    elapsed = time.perf_counter() - started
    completion = int(usage.get("completion_tokens") or 0)
    ttft = first_token - started if first_token is not None else elapsed
    return {
        "latency_seconds": elapsed,
        "ttft_seconds": ttft,
        "completion_tokens": completion,
        "tokens_per_second": completion / elapsed if completion else 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark jarvis-inference.")
    parser.add_argument("model")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--max-tokens", type=int, default=64)
    args = parser.parse_args()

    unload_probe = request(args.base_url, args.model, args.max_tokens, args.api_key, 0)
    cold = request(args.base_url, args.model, args.max_tokens, args.api_key, 0)
    warm = [
        request(args.base_url, args.model, args.max_tokens, args.api_key, "30m")
        for _ in range(max(1, args.runs))
    ]
    latencies = [item["latency_seconds"] for item in warm]
    ttfts = [item["ttft_seconds"] for item in warm]
    throughput = [item["tokens_per_second"] for item in warm if item["tokens_per_second"]]
    result = {
        "model": args.model,
        "unload_probe": unload_probe,
        "cold": cold,
        "warm": {
            "runs": len(warm),
            "ttft_p50_seconds": percentile(ttfts, 0.50),
            "ttft_p95_seconds": percentile(ttfts, 0.95),
            "latency_p50_seconds": percentile(latencies, 0.50),
            "latency_p95_seconds": percentile(latencies, 0.95),
            "latency_p99_seconds": percentile(latencies, 0.99),
            "tokens_per_second_p50": percentile(throughput, 0.50) if throughput else 0.0,
            "tokens_per_second_mean": statistics.mean(throughput) if throughput else 0.0,
        },
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
