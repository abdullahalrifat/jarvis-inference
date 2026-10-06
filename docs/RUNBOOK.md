# Operations runbook

## Daily

- Check container status and gateway readiness.
- Check free disk and available RAM.
- Confirm model verification remains green.
- Review inference errors and circuit-breaker openings.

## Weekly

- Run a warm benchmark for qwen3:1.7b.
- Benchmark qwen3:4b when it is actively used.
- Review TTFT, p95 latency, throughput and resource trends.
- Confirm backups exist.

## Monthly

- Review dependency and security updates.
- Review Docker base-image and Ollama digest updates.
- Perform a restore drill.
- Review model registry changes before accepting a new digest.

## Safe model update

1. Pull the candidate model explicitly.
2. Record the reported digest.
3. Benchmark cold and warm behavior.
4. Compare against the current baseline.
5. Update models/manifest.yaml.
6. Deploy through upgrade-optiplex.

## Capacity policy

This VM is intentionally single-generation. A second concurrent generation is a capacity regression unless a benchmark on the real hardware proves otherwise.

Preferred optimization order:

1. Keep one model loaded.
2. Keep routine traffic on qwen3:1.7b.
3. Use qwen3:4b when reasoning quality justifies latency.
4. Tune context length for actual workloads.
5. Increase CPU/RAM only after measurements show it is useful.
