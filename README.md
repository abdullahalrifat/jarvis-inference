# jarvis-inference

Production-grade local inference gateway for the Jarvis stack.

```
Jarvis -> AI Stack -> jarvis-inference -> Ollama / llama.cpp
```

- OpenAI-compatible chat completions with streaming SSE.
- Concrete model names only; no agent aliases.
- Ollama-first CPU deployment with optional llama.cpp.
- Bounded concurrency and container-aware memory admission.
- Liveness/readiness probes, API-key auth and request IDs.
- Prometheus metrics for latency, tokens, queueing and resource pressure.
- Docker Compose deployment tuned for a 16 GB CPU-only OptiPlex.

## OptiPlex 7040 / 16 GB baseline

Use `qwen3:1.7b` by default and `qwen3:4b` for explicitly heavier work. Keep one model loaded and one request active at a time. Never expose Ollama port 11434.

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

## Operations

```bash
./scripts/status.sh
./scripts/smoke-test.sh
./scripts/benchmark.sh qwen3:1.7b
docker compose -f docker/docker-compose.yml logs -f jarvis-inference
```
