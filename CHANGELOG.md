# Changelog

## 0.5.0

### Breaking / wire-contract changes

- InferenceError responses now return the OpenAI error envelope
  (`{"error": {"code", "message", "retryable", "request_id"}}`) instead of
  FastAPI's `{"detail": ...}` shape, so OpenAI-SDK clients get native error
  handling across non-streaming and streaming paths.
- Previously tolerated-but-unimplemented chat parameters (`n`, `logprobs`,
  `top_logprobs`, `logit_bias`, `presence_penalty`, `frequency_penalty`) are
  now rejected with an OpenAI-format `400 UNSUPPORTED_PARAMETER` instead of
  being silently dropped.
- A backend stream that ends without its terminal `done` event now fails with
  `502 STREAM_INCOMPLETE` (retryable) instead of being counted as a success.
- `POST /v1/*` request bodies larger than `MAX_REQUEST_BODY_MIB` (default 8)
  are rejected with `413 REQUEST_TOO_LARGE` before validation.
- Prompts that do not fit the effective context window are rejected with
  `400 CONTEXT_LIMIT_EXCEEDED` at admission instead of being silently
  truncated by the backend with HTTP 200.

### Streaming compliance

- Malformed backend SSE lines are skipped and logged instead of aborting an
  otherwise healthy stream.
- Ollama's `done_reason` is mapped exactly like the non-streaming path, so
  tool calls finish as `finish_reason: "tool_calls"` in streaming too.
- Streaming tool calls are emitted as OpenAI-indexed deltas
  (`{index, id, type, function:{name, arguments}}`) so OpenAI-SDK stream
  parsers work.
- `stream_options.include_usage` is honored with a final usage-only chunk
  (empty choices); without it the usage object stays inline on the final
  chunk.

### Ops / reliability

- `MAX_QUEUE_SIZE=0` is clamped to 1 (`asyncio.Queue` treats maxsize=0 as
  unbounded), restoring the bounded-queue guarantee.
- uvicorn starts with `--timeout-graceful-shutdown 25` (under the Compose
  30s `stop_grace_period`) so in-flight generations finish or fail cleanly
  instead of being killed mid-stream.
- The ollama container now receives the recorded `OLLAMA_NUM_THREADS` /
  `OLLAMA_KV_CACHE_TYPE` operator knobs.
- Compose and Dockerfile healthchecks probe `/ready` (backend-aware) instead
  of `/health`.
- Falsy `keep_alive` (0 = unload immediately) no longer falls back to the
  configured residency default; the `think` flag is only sent to
  thinking-capable model families.
- `ACTIVE_REQUEST_AGE` tracks the oldest active entry instead of being
  stomped to zero on every admission.
- The OpenAPI version metadata now tracks the installed package version
  instead of a hardcoded constant.

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
