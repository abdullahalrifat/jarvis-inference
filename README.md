# jarvis-inference

Production-grade local inference gateway for the Jarvis stack.

```
Jarvis -> AI Stack -> jarvis-inference -> Ollama / llama.cpp
```

## What this server provides

- OpenAI-compatible `/v1/chat/completions` with SSE streaming.
- Concrete model IDs only; no agent aliases.
- Ollama-first CPU deployment with optional llama.cpp.
- Bounded concurrency and queue backpressure.
- Container-aware memory admission.
- Persistent HTTP connection pooling to avoid a new TCP connection per inference.
- Request IDs on success, streaming, and errors.
- Prometheus metrics for latency, queue wait, tokens, active requests and resource pressure.
- Liveness/readiness endpoints.
- API-key authentication.
- Graceful shutdown and backend connection cleanup.
- Docker Compose deployment tuned for a 16 GB CPU-only OptiPlex 7040.

## OptiPlex 7040 / 16 GB baseline

The recommended profile is deliberately conservative:

- `qwen3:1.7b` as the default fast model.
- `qwen3:4b` for explicitly heavier reasoning.
- One active generation at a time.
- One Ollama model loaded at a time.
- 8-request bounded queue.
- Ollama receives ~3 CPU cores and up to 10 GiB RAM.
- The gateway is kept below 1 GiB RAM and uses very little CPU.
- Ollama model keep-alive defaults to 30 minutes to avoid repeated model reloads during normal personal use.

Do not expose Ollama port `11434`. Only expose the gateway.

## Quick start

```bash
git clone https://github.com/abdullahalrifat/jarvis-inference.git
cd jarvis-inference
./scripts/install-optiplex.sh
./scripts/smoke-test.sh
```

Set `INFERENCE_API_KEY` before exposing the gateway outside localhost.

## AI Stack

```
INFERENCE_BASE_URL=http://jarvis-inference:8080/v1
INFERENCE_API_KEY=<same key>
DEFAULT_MODEL=qwen3:1.7b
AGENT_REASONING_MODEL=qwen3:4b
```

For separate Compose projects, attach them to the same external Docker network and use the gateway container name.

## Performance model

This gateway intentionally does **not** try to compete with GPU inference servers by increasing concurrency. On the CPU-only OptiPlex, concurrent generation usually makes latency and memory pressure worse.

The hot path is:

1. Validate the concrete model ID.
2. Apply bounded queue admission.
3. Wait for the single inference slot.
4. Check memory pressure.
5. Reuse a persistent HTTP connection to Ollama.
6. Stream tokens immediately to the caller.
7. Record latency, queue wait and token metrics.
8. Release the slot even on cancellation or backend failure.

The backend HTTP clients use connection pooling, short connection timeouts and `trust_env=False` so local Ollama traffic is not accidentally routed through a system proxy.

## Supported generation controls

The gateway accepts common controls and maps them to Ollama:

- `temperature`
- `top_p`
- `top_k`
- `min_p`
- `seed`
- `num_ctx`
- `repeat_penalty`
- `stop`
- `max_tokens`
- `keep_alive`

Unknown OpenAI-compatible fields are still accepted by the request schema so the gateway can evolve without unnecessary client breakage.

## Observability

```bash
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8080/ready
./scripts/status.sh
```

Prometheus metrics are available at `/metrics`. The authenticated runtime endpoint is:

```
GET /v1/inference/status
```

Important metrics include:

- `inference_requests_total`
- `inference_request_duration_seconds`
- `inference_queue_wait_seconds`
- `inference_queue_depth`
- `inference_active_requests`
- `inference_tokens_total`
- `inference_resource_rejections_total`

## Benchmarking

```bash
./scripts/benchmark.sh qwen3:1.7b
./scripts/benchmark.sh qwen3:4b
```

Run both models after a cold start and again after they are warm. Model-load time and warm-token throughput are different workloads and should not be compared as if they were the same.

## Development

```bash
python -m pip install -e '.[dev]'
python -m ruff check .
python -m ruff format --check .
python -m pytest -q --cov=inference --cov-report=term-missing
```

`pyproject.toml` is the source of truth for package metadata and dependencies. `requirements.txt` is provided as a simple runtime deployment file.

## Security

- The gateway binds to localhost by default through Docker Compose.
- Ollama is not published to the host.
- API-key authentication is available for remote/internal network exposure.
- Containers use a non-root inference user, read-only filesystem, no-new-privileges and bounded resources.
- Do not put secrets in Git; use `.env` for deployment credentials.
