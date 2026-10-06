# jarvis-inference

Production-grade, CPU-optimized local inference gateway for the Jarvis stack.

```
Jarvis -> AI Stack -> jarvis-inference -> Ollama / llama.cpp
```

## World-class runtime features

- OpenAI-compatible `/v1/chat/completions` with streaming SSE.
- Concrete model IDs only; no agent aliases.
- OpenAI function/tool calling and `response_format` JSON / JSON Schema mapping to Ollama.
- Model lifecycle state: configured, installed, loaded/warm, cold requests and model transitions.
- Proper readiness: backend health, configured model availability and circuit state.
- Persistent HTTP/keep-alive connection pools.
- Bounded queue + single-generation scheduling tuned for the 4-core/16 GiB OptiPlex.
- Circuit breaker with half-open recovery.
- Cancellation-safe cleanup for queue slots, semaphores and active-request metrics.
- TTFT, generation duration, token throughput, queue wait, model-load and resource telemetry.
- Prometheus metrics plus a ready-to-import Grafana dashboard.
- Repeatable cold/warm benchmark suite with p50/p95/p99 latency and TTFT.
- Reproducible production images pinned by digest.
- Release automation with Python artifacts, GHCR image, SBOM, Trivy scanning and GitHub artifact attestations.
- Dependabot, dependency review, pip-audit, CodeQL and filesystem security scanning.
- Non-root, read-only inference container with bounded CPU/RAM.

## OptiPlex 7040 / 16 GiB baseline

The production profile is deliberately conservative:

- `qwen3:1.7b` = default fast model.
- `qwen3:4b` = explicit heavier reasoning model.
- One active generation.
- One loaded model.
- Eight queued requests.
- Ollama gets about 3 CPU cores and 10 GiB RAM.
- Gateway stays below 1 GiB.
- 30-minute keep-alive avoids unnecessary reloads during normal personal use.

Do not expose Ollama port `11434`; expose only the gateway.

## Lifecycle and readiness

`GET /ready` is a real readiness probe rather than a process-alive check. It requires:

1. Backend reachable.
2. Circuit closed / probeable.
3. Every configured model installed on the selected backend.

`GET /v1/inference/status` exposes active model, available models, loaded models, warm/cold request counts, queue state, circuit state and resource telemetry.

A request records whether the target model was already loaded before generation. A successful request marks that model warm; with `MAX_LOADED_MODELS=1`, switching models records the previous model as evicted.

## OpenAI compatibility

Supported request fields include:

- `temperature`, `top_p`, `top_k`, `min_p`, `seed`
- `num_ctx`, `repeat_penalty`, `stop`, `max_tokens`
- `tools`, `tool_choice`
- `response_format.type=json_object`
- `response_format.type=json_schema`
- `stream`, `keep_alive`

Tool calls are returned in the OpenAI `message.tool_calls` shape. Structured output schemas are translated to Ollama's native `format` contract.

## Performance and benchmarking

The benchmark separates cold and warm workloads. Cold runs use `keep_alive=0`; warm runs use the configured keep-alive.

```bash
./scripts/benchmark.sh qwen3:1.7b
./scripts/benchmark.sh qwen3:4b
```

The underlying suite measures:

- TTFT
- total latency
- completion token count
- tokens/sec
- warm p50/p95/p99

The server also exports backend-reported Ollama timings when available. Ollama exposes load, prompt-evaluation and generation durations in nanoseconds, including final streaming usage data. citeturn3search0turn3search2

For this OptiPlex, optimize for **stable warm latency and throughput**, not concurrency. Increasing generation concurrency generally makes a 4-core CPU workload slower and more memory-sensitive.

## Observability

Prometheus metrics include:

- `inference_requests_total`
- `inference_request_duration_seconds`
- `inference_queue_wait_seconds`
- `inference_time_to_first_token_seconds`
- `inference_generation_duration_seconds`
- `inference_tokens_total`
- `inference_tokens_per_second`
- `inference_model_load_seconds`
- `inference_queue_depth`
- `inference_active_requests`
- `inference_backend_errors_total`
- `inference_resource_rejections_total`
- `inference_circuit_open`
- `inference_model_warm`
- `inference_host_cpu_percent`
- `inference_host_memory_available_gib`
- `inference_container_memory_available_gib`

Import `observability/grafana/jarvis-inference.json` into Grafana and point it at your Prometheus datasource.

If `INFERENCE_API_KEY` is set, Prometheus must send the same bearer token to `/metrics`.

## Security and supply chain

- Gateway binds to localhost in Compose.
- Ollama is never published to the host.
- API-key authentication is available for all authenticated API/metrics endpoints.
- Containers use a non-root user, read-only filesystem, no-new-privileges and resource limits.
- Python and Ollama production images are pinned by digest.
- Releases publish Python distributions and a GHCR image.
- Release builds generate SPDX SBOMs and scan the container with Trivy.
- GitHub artifact attestations establish release provenance.
- PR/main security automation runs dependency review, pip-audit, Trivy filesystem scanning and CodeQL.
- Dependabot keeps Python, Docker and GitHub Action dependencies current.

GitHub recommends artifact attestations for establishing build provenance and supports SBOM attestations for release artifacts. citeturn2search0turn2search5

## AI Stack

```
INFERENCE_BASE_URL=http://jarvis-inference:8080/v1
INFERENCE_API_KEY=<same key>
DEFAULT_MODEL=qwen3:1.7b
AGENT_REASONING_MODEL=qwen3:4b
```

Use direct model IDs. Do not reintroduce aliases such as `orchestrator` or `qwen3-4b`.

For separate Compose projects, attach them to the same external Docker network and use the gateway container name.

## Quick start

```bash
git clone https://github.com/abdullahalrifat/jarvis-inference.git
cd jarvis-inference
./scripts/install-optiplex.sh
./scripts/smoke-test.sh
```

Set `INFERENCE_API_KEY` before remote exposure.

## Development gates

```bash
python -m pip install -e '.[dev]'
python -m ruff check .
python -m ruff format --check .
python -m pytest -q --cov=inference --cov-report=term-missing --cov-fail-under=70
```

`pyproject.toml` is the source of truth for package metadata and dependencies. `requirements.txt` is only a convenient runtime deployment file.

## Docker reproducibility

The Dockerfile and Compose file pin their production base/runtime images by immutable digest. Renovate/Dependabot should be used to refresh those pins deliberately rather than using moving `latest` tags.

The current Ollama production image is pinned to version `0.35.1`; the official image publishes platform-specific manifests, so the digest is deliberately explicit for reproducible amd64 deployment. citeturn7view0
