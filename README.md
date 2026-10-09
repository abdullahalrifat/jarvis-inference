# jarvis-inference

Current release candidate: **0.3.3** (authentication fail-closed and timeout replay protection). See [CHANGELOG.md](CHANGELOG.md) for release notes.

Production-grade CPU inference gateway for the Jarvis stack.

## Queueing and CPU-only operation

The gateway intentionally runs one generation at a time on small CPU-only hosts. A bounded waiting queue prevents unbounded work accumulation; `QUEUE_TIMEOUT_SECONDS` controls how long a request waits for a slot (default: 90 seconds), while `MAX_QUEUE_SIZE` bounds waiting requests separately from the active inference slot. Queue-depth telemetry counts waiting requests, not the active generation. Queue timeout and queue-full responses are explicit pre-generation rejections and include `Retry-After` guidance. Clients must not retry ambiguous generation/read timeouts because the backend may already have executed the request.

Backend model-state refreshes occur only after a request owns the inference slot, avoiding redundant concurrent refresh work while another generation is active. Increasing the queue deadline improves tolerance to normal long generations; it does not increase throughput.

## Embedding efficiency

Embedding requests are sent to Ollama as a batch rather than one HTTP request per text. Response order is preserved, incomplete batches fail explicitly, and an empty batch performs no backend request. Batching reduces request overhead; it does not claim to eliminate embedding compute.

## Architecture

```text
Jarvis CLI (local agent)           AI Stack (optional remote control plane)
          |                                      |
          +------------------+-------------------+
                             v
                     jarvis-inference
                    OpenAI-compatible API
                             |
                           Ollama
```

The dedicated inference VM owns model execution. Jarvis and AI Stack are independent sibling consumers of the gateway; neither consumer runs Ollama or LiteLLM. Jarvis local execution must remain usable when AI Stack is stopped. The gateway owns the model allowlist, bounded queue, concurrency, backend timeouts and resource limits.

## Production profile

Recommended CPU-only VM:

- 4 vCPU
- 10-12 GiB RAM
- Ollama: 2.75 CPU / 9 GiB RAM
- Gateway: 0.50 CPU / 512 MiB RAM
- One active generation
- One loaded model
- Queue size 8
- Context length 8192
- Ollama keep-alive 30 minutes

Configured models:

- qwen3:1.7b — default fast model
- qwen3:4b — reasoning model
- nomic-embed-text — embeddings

## Deployment layout

The deployment surface is intentionally minimal:

```text
.
├── docker-compose.yml
├── docker/
│   └── Dockerfile
├── scripts/
│   └── install.sh
├── .env.example
├── models/manifest.yaml
└── inference/
```

There is one operational script: `scripts/install.sh`. Routine lifecycle operations use Docker Compose directly.

## Install

```bash
git clone https://github.com/abdullahalrifat/jarvis-inference.git
cd jarvis-inference
cp .env.example .env
```

For a dedicated inference VM serving either standalone Jarvis or AI Stack, set:

```env
INFERENCE_BIND_ADDRESS=0.0.0.0
INFERENCE_API_KEY=<long-random-secret>
```

Keep TCP 8080 restricted to the private network or trusted clients. Ollama port 11434 is never published.

Install:

```bash
bash scripts/install.sh
```

The installer validates Docker/Compose, validates the Compose file, builds the gateway, starts Ollama, ensures configured models are present, waits for readiness, and runs authenticated smoke checks.

## Deployment lifecycle

All commands below are run from the repository root on the dedicated inference VM.

### 1. First deployment

Install Docker Engine and Docker Compose v2 first, then:

```bash
git clone https://github.com/abdullahalrifat/jarvis-inference.git
cd jarvis-inference
cp .env.example .env
chmod 600 .env
```

For a dedicated inference VM serving Jarvis or AI Stack from another VM, configure:

```env
INFERENCE_BIND_ADDRESS=0.0.0.0
INFERENCE_API_KEY=<long-random-secret>
```

Keep TCP 8080 restricted to trusted private-network clients. Ollama port 11434 must remain internal.

Run the idempotent installer:

```bash
bash scripts/install.sh
```

Verify:

```bash
docker compose ps
curl -sS http://127.0.0.1:8080/health
curl -sS http://127.0.0.1:8080/ready
curl -sS -H "Authorization: Bearer $INFERENCE_API_KEY" http://127.0.0.1:8080/v1/capabilities
```

From a remote Jarvis/AI Stack VM:

```bash
curl -sS http://<INFERENCE_VM_IP>:8080/ready
```

### 2. Pull the latest changes

The installer does not replace your `.env`. Before updating:

```bash
cd ~/docker/jarvis-inference
git status
git pull --ff-only
```

If `git status` shows local source changes, stop and review them before pulling. Never use `git reset --hard` unless you intentionally want to discard local changes.

### 3. Re-deploy after pulling changes

Use the same installer:

```bash
bash scripts/install.sh
```

It validates Compose, rebuilds the gateway, starts the services, ensures configured Ollama models exist, waits for readiness, and runs smoke checks.

For a source-only gateway change, you can rebuild/recreate just the gateway:

```bash
docker compose build --pull jarvis-inference
docker compose up -d --force-recreate jarvis-inference
```

Do not remove the Ollama volume during normal redeployment; otherwise the models will need to be downloaded again.

### 4. Normal operations

Check status:

```bash
docker compose ps
```

View gateway logs:

```bash
docker compose logs --tail=200 jarvis-inference
```

View Ollama logs:

```bash
docker compose logs --tail=200 ollama
```

Follow logs:

```bash
docker compose logs -f jarvis-inference
```

Restart only the gateway:

```bash
docker compose restart jarvis-inference
```

Restart both services:

```bash
docker compose restart ollama jarvis-inference
```

### 5. Shut down the inference stack

To stop the containers while preserving models and configuration:

```bash
docker compose stop
```

To stop and remove the containers/network while preserving the named Ollama model volume:

```bash
docker compose down
```

This is the preferred shutdown before VM maintenance or reboot.

Start again without rebuilding:

```bash
docker compose up -d
```

### 6. Full cleanup

For a normal application cleanup, use:

```bash
docker compose down
```

This removes containers and the Compose network but **does not remove the Ollama model volume**.

To deliberately remove the downloaded models as well:

```bash
docker compose down -v
```

This is destructive: all Ollama model data in the Compose volume will be deleted and the next deployment will download the models again.

Do not run `docker system prune --volumes` as part of routine maintenance because it can remove unrelated Docker resources.

### 7. Complete removal from the VM

If the inference VM is being retired and you want to remove the application, containers, network, and model volume:

```bash
cd ~/docker/jarvis-inference
docker compose down -v
cd ..
rm -rf jarvis-inference
```

Back up the production `.env` securely before doing this if the VM may need to be rebuilt.

### 8. Recovery after a VM reboot

Docker should restart the Compose services according to the Compose restart policy. Verify:

```bash
cd ~/docker/jarvis-inference
docker compose ps
curl -sS http://127.0.0.1:8080/ready
```

If the stack did not start:

```bash
docker compose up -d
```

If the gateway image or source needs rebuilding:

```bash
bash scripts/install.sh
```

### 9. Troubleshooting remote connection refused

On the inference VM:

```bash
docker compose ps
hostname -I
```

The gateway should show a publication similar to:

```text
0.0.0.0:8080->8080/tcp
```

Check the bind setting:

```bash
grep '^INFERENCE_BIND_ADDRESS=' .env
```

For cross-VM access it should be:

```env
INFERENCE_BIND_ADDRESS=0.0.0.0
```

Then recreate the gateway:

```bash
docker compose up -d --force-recreate jarvis-inference
```

From the client VM:

```bash
curl -sS http://<INFERENCE_VM_IP>:8080/ready
```

If local readiness works but remote access fails, check the VM firewall and private-network routing. Do not expose port 11434.

## Operations

From the repository root:

```bash
docker compose ps
docker compose logs --tail=100 jarvis-inference
docker compose logs --tail=100 ollama
docker compose restart jarvis-inference
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8080/ready
```

For a remote client, use the VM's private IP instead of 127.0.0.1 and include the inference API key for authenticated endpoints.

Upgrade the application:

```bash
git pull --ff-only
bash scripts/install.sh
```

This rebuilds the gateway while preserving the Ollama model volume.

## Model integrity

`models/manifest.yaml` is the deployment model record. Model digest changes should be reviewed deliberately rather than silently accepted.

The installer ensures the configured model names exist, but it does not overwrite the manifest digest automatically.

## Security

- Loopback binding is the default.
- Remote binding is explicit through `INFERENCE_BIND_ADDRESS`.
- Remote deployments require `INFERENCE_API_KEY`.
- Ollama is not exposed outside the Docker network.
- Gateway runs non-root with a read-only filesystem and no-new-privileges.
- Production container images are pinned by digest.
- Docker logs have bounded rotation.
- CI includes tests, security scanning and release checks.

## Development

```bash
python -m pip install -e '.[dev]'
python -m ruff check .
python -m ruff format --check .
python -m pytest -q --cov=inference --cov-report=term-missing --cov-fail-under=70
```

## Operational validation

A target-host validation surface is now available under `scripts/world_class_check.sh`, `scripts/benchmark.sh` and `scripts/soak.sh`. Production certification requires retained benchmark/soak evidence on the actual inference VM; CI alone is insufficient.
