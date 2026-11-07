# Changelog

## 0.4.0

### Features

- First-class reasoning-model support: `/v1/chat/completions` accepts a `think` parameter (`true`/`false`). Qwen3-family models are forced to explicit non-thinking mode by default (`OLLAMA_DEFAULT_THINK`, default `false`) so callers no longer silently burn the token budget on reasoning.
- Reasoning output is surfaced OpenAI-style as `reasoning_content` in both non-streaming messages and streaming deltas when thinking is enabled, instead of empty content blocks.

### Ops notes

- Optimized CPU profile on modern hosts: measured ~26 tok/s on `qwen3:4b` and ~14 tok/s on `qwen3:8b` with `OLLAMA_NUM_THREADS=8` on an i7-14700; thread counts beyond 8 collapse restartless throughput because decode is memory-bandwidth bound.
- Model registry now provisioned with `qwen3:8b`; recorded in `models/manifest.yaml`.

## 0.3.3

### Reliability

- Acquire the bounded inference slot before refreshing backend model state, preventing concurrent queued requests from duplicating model-state checks; release the slot even if preparation fails.
- Count only waiting requests in queue depth/capacity; the active inference slot is reported separately.
- Reuse cached model discovery during readiness probes instead of forcing redundant backend calls, and align OpenAPI version metadata with package version 0.3.3.
- Honor `MAX_LOADED_MODELS` in Compose while preserving the safe default of one model; this enables measured two-model residency experiments without changing default memory behavior.
- Bound per-request context overrides and embedding batch size before queue admission to protect CPU-only hosts from oversized requests.
- Include timed-out requests in queue-wait latency histograms so observed wait distributions are not biased toward successful admissions.
- Increase the default queue wait to 90 seconds to match realistic CPU-only generation latency while retaining bounded queue size and single-request concurrency.
- Return `Retry-After` guidance for explicit queue-full and queue-timeout rejections, including streaming requests before SSE headers are committed.

### Tests

- Cover serialized model preparation and queue/slot cleanup after a waiting request times out.


## 0.3.2

### Performance and reliability

- Batch embedding inputs into one Ollama `/api/embed` request, preserving input order and rejecting incomplete batches.
- Return immediately for an empty embedding batch without waking the backend.

### Tests

- Cover batching, response ordering, empty input, and incomplete backend responses.


## 0.3.1

### Security

- Fail startup when `INFERENCE_API_KEY` is missing unless the explicit development-only `INFERENCE_ALLOW_INSECURE_NO_AUTH=true` override is set.
- Return 503 when authentication is not configured and 401 when configured credentials are missing or invalid.

### Reliability

- Add regression coverage ensuring ambiguous backend generation timeouts are not automatically replayed.
- Add security configuration and authentication tests.
