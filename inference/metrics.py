from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, generate_latest

REQUESTS = Counter("inference_requests_total", "Inference requests.", ["model", "status"])
LATENCY = Histogram("inference_request_duration_seconds", "Inference request duration.", ["model"])
TOKENS = Counter("inference_tokens_total", "Inference tokens.", ["model", "kind"])
QUEUE = Gauge("inference_queue_depth", "Current queued requests.")
RESOURCE_REJECTIONS = Counter("inference_resource_rejections_total", "Resource-pressure rejections.")
ACTIVE_MODEL = Gauge("inference_active_model", "Whether the model is active.", ["model"])


def render() -> bytes:
    return generate_latest()
