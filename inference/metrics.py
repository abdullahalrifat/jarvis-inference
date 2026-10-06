from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, generate_latest

REQUESTS = Counter("inference_requests_total", "Inference requests.", ["model", "status"])
LATENCY = Histogram("inference_request_duration_seconds", "Inference request duration.", ["model"])
QUEUE_WAIT = Histogram(
    "inference_queue_wait_seconds", "Time spent waiting for an inference slot.", ["model"]
)
TTFT = Histogram(
    "inference_time_to_first_token_seconds",
    "Time from backend start to first streamed token.",
    ["model"],
)
GENERATION_DURATION = Histogram(
    "inference_generation_duration_seconds",
    "Backend generation duration in seconds.",
    ["model"],
)
TOKENS = Counter("inference_tokens_total", "Inference tokens.", ["model", "kind"])
TOKENS_PER_SECOND = Histogram(
    "inference_tokens_per_second",
    "Observed output token generation rate.",
    ["model"],
)
MODEL_LOAD = Histogram(
    "inference_model_load_seconds",
    "Observed model load duration.",
    ["model"],
)
QUEUE = Gauge("inference_queue_depth", "Current queued requests.")
ACTIVE_REQUESTS = Gauge("inference_active_requests", "Currently executing inference requests.")
RESOURCE_REJECTIONS = Counter(
    "inference_resource_rejections_total", "Resource-pressure rejections."
)
BACKEND_ERRORS = Counter(
    "inference_backend_errors_total", "Backend failures and timeouts.", ["backend", "code"]
)
CIRCUIT_STATE = Gauge(
    "inference_circuit_open",
    "Whether the backend circuit is open (1) or closed (0).",
    ["backend"],
)
ACTIVE_MODEL = Gauge("inference_active_model", "Whether the model is active.", ["model"])


def render() -> bytes:
    return generate_latest()
