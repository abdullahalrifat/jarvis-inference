# jarvis-inference

Production-grade CPU inference gateway for the Jarvis stack.

Architecture:

    Jarvis -> AI Stack -> jarvis-inference -> Ollama / llama.cpp

## Production profile

This repository is optimized for a dedicated CPU-only inference VM rather than a shared 4-core host.

Recommended Proxmox starting point:

- VM: 4 vCPU, 10-12 GiB RAM.
- Ollama: 2.75 CPU, 9 GiB RAM.
- Gateway: 0.50 CPU, 512 MiB RAM.
- One active generation.
- One loaded model.
- Queue size 8.
- Context length 8192.
- Ollama keep-alive 30 minutes.
- SSD-backed Ollama volume.

The VM is intentionally provisioned above the container limits so Linux, Docker, page cache and upgrades retain headroom.

Configured models:

- qwen3:1.7b — default fast model.
- qwen3:4b — explicit reasoning model.

Do not reintroduce aliases such as orchestrator or qwen3-4b.

## Runtime features

- OpenAI-compatible chat completions with SSE streaming.
- Tool/function calling and JSON/JSON Schema structured output.
- Direct model IDs only.
- Model lifecycle tracking: installed, loaded/warm, cold requests and evictions.
- Real readiness endpoint separate from liveness.
- Persistent HTTP connection pools.
- Bounded queue and single-generation scheduler.
- Circuit breaker with recovery.
- Cancellation-safe request cleanup.
- TTFT, generation duration, queue wait and token throughput metrics.
- Prometheus metrics and Grafana dashboard.
- Cold/warm benchmarking.
- API-key authentication.
- Non-root, read-only gateway container.
- Pinned production container images.
- SHA-pinned GitHub Actions.
- SBOM, vulnerability scanning and artifact provenance.

## Model integrity

models/manifest.yaml is the deployment lock file.

The workflow is:

    bash scripts/download-models.sh
    bash scripts/lock-models.sh
    bash scripts/verify-models.sh

The first lock operation is a deliberate trust ceremony. Review the installed model digest before committing the manifest. Future deployments fail if the installed digest differs from the locked digest.

An empty digest is intentionally considered unpinned and is rejected by verify-models.sh. This prevents a tag from silently moving to a different model artifact.

## Installation

    git clone https://github.com/abdullahalrifat/jarvis-inference.git
    cd jarvis-inference
    cp .env.example .env

Set INFERENCE_API_KEY before remote exposure, then:

    bash scripts/config-doctor.sh
    bash scripts/install-optiplex.sh

Only the gateway is published. Ollama port 11434 is never published.

## Production operations

Configuration:

    bash scripts/config-doctor.sh
    bash scripts/status-optiplex.sh

Readiness:

    bash scripts/wait-ready.sh

Models:

    bash scripts/download-models.sh
    bash scripts/verify-models.sh

Backup:

    bash scripts/backup.sh
    bash scripts/restore.sh "$HOME/jarvis-inference-backups/latest"

Upgrade:

    bash scripts/upgrade-optiplex.sh <reviewed-ref>

Rollback:

    bash scripts/rollback-optiplex.sh <known-good-sha>

Watchdog:

    bash scripts/watchdog.sh

The watchdog checks free disk, available RAM, container state and gateway readiness. Schedule it every five minutes with systemd or cron.

## Transactional upgrades

upgrade-optiplex.sh is designed as a deployment transaction:

1. Require a clean Git tree.
2. Back up configuration.
3. Run the configuration doctor.
4. Fetch the reviewed target.
5. Build the gateway image.
6. Restart the stack.
7. Wait for readiness.
8. Verify model digests.
9. Run the smoke test.
10. Automatically return to the previous commit if build, readiness or model verification fails.

This keeps code upgrades separate from model upgrades.

## Backup and disaster recovery

Normal backups contain:

- .env and deployment configuration.
- Docker Compose and Dockerfile.
- model manifest.
- rendered Compose configuration.
- Git revision.
- SHA-256 checksums.

Model data is excluded by default because it is large and reproducible. For a full model-volume backup:

    BACKUP_MODELS=1 bash scripts/backup.sh

See docs/PRODUCTION.md, docs/RUNBOOK.md and docs/DISASTER-RECOVERY.md for the complete operating procedures.

## Benchmarking and regression detection

Run:

    bash scripts/benchmark.sh qwen3:1.7b
    bash scripts/benchmark.sh qwen3:4b

Results are stored under benchmarks/ and ignored by Git.

Compare a candidate against a known-good baseline:

    python3 scripts/benchmark-regression.py baseline.json candidate.json

Default rejection thresholds:

- warm p50/p95 latency: +20%.
- warm p50 TTFT: +25%.
- warm p50 throughput: -15%.

These are guardrails, not promises. Tune them from several runs on the real VM.

## Security

- Gateway binds to loopback in the default Compose deployment.
- Ollama is not exposed.
- Remote gateway access requires an API key.
- Containers use non-root/read-only/no-new-privileges controls.
- Docker logs have bounded rotation.
- Production images are pinned by digest.
- GitHub Actions are pinned to immutable commit SHAs.
- pip-audit and Trivy run in CI.
- Release artifacts receive SBOMs and GitHub artifact attestations.
- Dependabot tracks Python, Docker and GitHub Action dependencies.

## AI Stack integration

Use direct model IDs:

    INFERENCE_BASE_URL=http://jarvis-inference:8080/v1
    INFERENCE_API_KEY=<same key>
    DEFAULT_MODEL=qwen3:1.7b
    AGENT_REASONING_MODEL=qwen3:4b

For separate Compose projects, connect both projects to the same private Docker network and address the gateway by its container/network name.

## Development gates

    python -m pip install -e '.[dev]'
    python -m ruff check .
    python -m ruff format --check .
    bash -n scripts/*.sh
    python -m pytest -q --cov=inference --cov-report=term-missing --cov-fail-under=70

pyproject.toml is the source of truth for package metadata and dependencies. requirements.txt is the runtime deployment convenience file.

## Production principles

1. Optimize for stable warm latency, not concurrency.
2. Keep one model loaded.
3. Prefer qwen3:1.7b for routine requests.
4. Use qwen3:4b when reasoning quality justifies its CPU cost.
5. Treat model digests as deployment inputs, not mutable configuration.
6. Benchmark before and after runtime/model changes.
7. Back up configuration before upgrades.
8. Roll back automatically when a deployment gate fails.
