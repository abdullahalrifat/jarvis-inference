# Inference world-class operations

The gateway is certified only when target-host evidence covers readiness after reboot, bounded queue behavior, cancellation, model warmup, 24h/72h soak and per-model benchmarks.

Run:
```bash
bash scripts/world_class_check.sh
bash scripts/benchmark.sh
DURATION_SECONDS=86400 bash scripts/soak.sh
```

Record each result with CPU/RAM, model manifest digest and git SHA. CI is necessary but does not replace target-hardware evidence.

Never expose Ollama port 11434. Remote gateway binding requires an API key and private-network firewalling. Restart/redeploy must preserve the Ollama volume.
