# jarvis-inference

Production-grade CPU inference gateway for the Jarvis stack.

## Architecture

    Jarvis / AI Stack
            |
            v
    jarvis-inference
            |
            v
         Ollama

The dedicated inference VM owns model execution. AI Stack and Jarvis do not run Ollama or LiteLLM.

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

For a dedicated inference VM serving another machine, set:

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
