# Production deployment

## Target VM

Run inference in its own VM so CPU scheduling and memory pressure are isolated from AI Stack and unrelated services.

Recommended Proxmox starting point:

- 4 vCPU assigned to the VM.
- 10-12 GiB VM RAM.
- Ollama container: 2.75 CPU and 9 GiB RAM.
- Gateway container: 0.50 CPU and 512 MiB RAM.
- SSD-backed Ollama volume.
- No GPU is assumed.
- One active generation and one loaded model.

The VM is intentionally provisioned slightly above the container budgets. Linux, Docker, filesystem cache and upgrades need headroom.

## First installation

1. Clone the repository.
2. Copy .env.example to .env.
3. Set INFERENCE_API_KEY before remote exposure.
4. For clients on another VM, set `INFERENCE_BIND_ADDRESS=0.0.0.0` in `.env`. The Compose default remains loopback for fail-closed local deployments.
5. Run:

    docker compose config --quiet
    bash scripts/install.sh

5. Inspect the model digests and run:

    inspect models/manifest.yaml
    inspect models/manifest.yaml

The first lock operation is a deliberate trust ceremony. Preserve the resulting manifest and review any future digest change.

## Networking

Only the gateway should be reachable by AI Stack. Ollama port 11434 is never published.

If the gateway is reachable outside the VM, require API-key authentication and TLS at the external boundary. Restrict TCP 8080 to the private network or trusted client IPs with the host/network firewall. Do not publish Prometheus metrics to the public internet.

## Operations commands

    docker compose ps
    docker compose config --quiet
    bash scripts/watchdog.sh
    back up .env and deployment configuration
    restore the repository and .env from your backup
    git pull --ff-only && bash scripts/install.sh
    git checkout <known-good-sha> && bash scripts/install.sh
    inspect models/manifest.yaml

## Resource policy

| Resource | Production budget |
| --- | ---: |
| VM CPU | 4 vCPU |
| VM RAM | 10-12 GiB |
| Ollama CPU | 2.75 |
| Ollama RAM | 9 GiB |
| Gateway CPU | 0.50 |
| Gateway RAM | 512 MiB |
| Generation concurrency | 1 |
| Queue | 8 |
| Loaded models | 1 |
| Context | 8192 |
| Keep alive | 30m |

The single-generation policy is intentional for a CPU-only deployment. Do not increase concurrency merely because the API queue is non-empty.

## Upgrade transaction

upgrade-optiplex performs:

1. Clean-tree validation.
2. Configuration backup.
3. Preflight checks.
4. Fetch of the target revision.
5. Gateway image rebuild.
6. Service restart.
7. Readiness check.
8. Model digest verification.
9. Smoke test.
10. Automatic rollback if build, readiness or model verification fails.

For explicit recovery, rollback-optiplex can restore a known-good commit.

## Backups

Normal backups include the environment file, deployment configuration, model manifest, rendered Compose configuration, Git revision and SHA-256 checksums.

Model-volume backup is optional because model data is large. Enable it with BACKUP_MODELS=1 when external registry access is unreliable or before major model changes.

Backup archives contain secrets because .env may contain the API key. Keep them mode 0700 and outside Git.

## Watchdog

Run watchdog.sh from a systemd timer or cron every five minutes. It checks:

- free disk;
- available RAM;
- both inference containers;
- gateway readiness.

The watchdog intentionally reports failures rather than trying to restart everything. Automatic restart policy belongs to Docker; destructive recovery should remain operator-controlled.

## Watchdog installation with systemd

If the deployment user can access the Docker socket:

    mkdir -p ~/.config/systemd/user
    cp deploy/systemd/user/jarvis-inference-watchdog.service ~/.config/systemd/user/
    cp deploy/systemd/user/jarvis-inference-watchdog.timer ~/.config/systemd/user/
    systemctl --user daemon-reload
    systemctl --user enable --now jarvis-inference-watchdog.timer

Enable lingering if the user service must continue without an interactive login:

    loginctl enable-linger "$USER"

## Benchmark policy

After a runtime, Docker image or model update:

    bash scripts/benchmark.sh qwen3:1.7b

Benchmark JSON is saved under benchmarks/ and ignored by Git. Keep a known-good baseline outside the repository and compare candidates with:

    python3 scripts/benchmark-regression.py baseline.json candidate.json

Default rejection thresholds are 20% latency, 25% TTFT and 15% throughput regression. Tune these from several real runs on the dedicated VM.

## Model lifecycle

The model manifest records the Ollama digest for each production model.

Safe update:

1. Pull the candidate model explicitly.
2. Inspect its digest.
3. Benchmark it.
4. Compare against the known-good baseline.
5. Update the manifest deliberately.
6. Deploy through the transaction process.

Never silently replace a digest.
