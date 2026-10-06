from __future__ import annotations
import argparse
import json
from pathlib import Path

def ratio(current: float, baseline: float) -> float:
    return current / baseline if baseline else 1.0

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--latency-regression", type=float, default=0.20)
    parser.add_argument("--ttft-regression", type=float, default=0.25)
    parser.add_argument("--throughput-regression", type=float, default=0.15)
    args = parser.parse_args()
    base = json.loads(args.baseline.read_text())
    cur = json.loads(args.candidate.read_text())
    b, c = base["warm"], cur["warm"]
    checks = [
        ("latency_p50", b["latency_p50_seconds"], c["latency_p50_seconds"], args.latency_regression, True),
        ("latency_p95", b["latency_p95_seconds"], c["latency_p95_seconds"], args.latency_regression, True),
        ("ttft_p50", b["ttft_p50_seconds"], c["ttft_p50_seconds"], args.ttft_regression, True),
        ("tokens_per_second_p50", b["tokens_per_second_p50"], c["tokens_per_second_p50"], args.throughput_regression, False),
    ]
    failures = []
    for name, old, new, limit, higher_is_bad in checks:
        r = ratio(new, old)
        bad = r > 1 + limit if higher_is_bad else r < 1 - limit
        print(f"{name}: baseline={old:.4f} candidate={new:.4f} ratio={r:.3f}")
        if bad:
            failures.append(name)
    if failures:
        raise SystemExit("Performance regression: " + ", ".join(failures))

if __name__ == "__main__":
    main()
