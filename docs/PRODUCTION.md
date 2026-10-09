# Production deployment

## Dedicated inference VM

Recommended CPU-only profile:

- 4 vCPU
- 10-12 GiB RAM
- Ollama: 2.75 CPU / 9 GiB RAM
- Gateway: 0.50 CPU / 512 MiB RAM
- SSD-backed Ollama volume
- One active generation and one loaded model

## Install

```bash
git clone https://github.com/abdullahalrifat/jarvis-inference.git
cd jarvis-inference
cp .env.example .env
```

For cross-VM access:

```env
INFERENCE_BIND_ADDRESS=0.0.0.0
INFERENCE_API_KEY=<long-random-secret>
INFERENCE_ALLOW_INSECURE_NO_AUTH=false
```

Restrict TCP 8080 to the private network or trusted client IPs. Never publish Ollama port 11434.

Run:

```bash
bash scripts/install.sh
```

The installer validates the deployment, builds the gateway, starts Ollama, ensures configured models exist, waits for readiness, and runs smoke checks. Set a non-empty `INFERENCE_API_KEY` before deploying; the service refuses startup without one unless the explicit development-only override is enabled.

## Operations

```bash
docker compose ps
docker compose logs --tail=100 jarvis-inference
docker compose logs --tail=100 ollama
docker compose restart jarvis-inference
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8080/ready
```

Upgrade:

```bash
git pull --ff-only
bash scripts/install.sh
```

The Ollama named volume is preserved across gateway rebuilds.

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

## Model integrity

`models/manifest.yaml` records production model identities and reviewed digests. Do not silently change a recorded digest.

The installer pulls only the configured model names from `.env`; model digest changes should be reviewed separately before updating the manifest.

## Security

- Loopback binding is the default.
- Remote binding is explicit.
- Startup fails closed if `INFERENCE_API_KEY` is empty, unless `INFERENCE_ALLOW_INSECURE_NO_AUTH=true` is explicitly selected for isolated local development.
- Remote deployments require API-key authentication.
- Ollama is never published.
- Gateway runs non-root, read-only and with no-new-privileges.
- Container images are pinned by digest.
- Keep port 8080 private and do not expose metrics publicly.
