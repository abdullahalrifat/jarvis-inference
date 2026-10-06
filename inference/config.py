from __future__ import annotations

import os
from dataclasses import dataclass


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


def _csv(name: str, default: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in os.getenv(name, default).split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    host: str = os.getenv("INFERENCE_HOST", "0.0.0.0")
    port: int = _int("INFERENCE_PORT", 8080)
    api_key: str = os.getenv("INFERENCE_API_KEY", "")
    max_concurrent_requests: int = max(1, _int("MAX_CONCURRENT_REQUESTS", 1))
    max_queue_size: int = max(0, _int("MAX_QUEUE_SIZE", 8))
    max_loaded_models: int = max(1, _int("MAX_LOADED_MODELS", 1))
    memory_budget_gb: float = max(0.5, _float("MEMORY_BUDGET_GB", 10.0))
    memory_headroom_gb: float = max(0.25, _float("MEMORY_HEADROOM_GB", 1.5))
    request_timeout_seconds: float = max(1.0, _float("REQUEST_TIMEOUT_SECONDS", 600.0))
    shutdown_timeout_seconds: float = max(1.0, _float("SHUTDOWN_TIMEOUT_SECONDS", 30.0))
    default_model: str = os.getenv("DEFAULT_MODEL", "qwen3:1.7b")
    ollama_url: str = os.getenv("OLLAMA_URL", "http://ollama:11434").rstrip("/")
    llamacpp_url: str = os.getenv("LLAMACPP_URL", "").rstrip("/")
    ollama_keep_alive: str = os.getenv("OLLAMA_KEEP_ALIVE", "10m")

    @property
    def models(self) -> tuple[str, ...]:
        return _csv("MODEL_REGISTRY", "qwen3:1.7b,qwen3:4b")

    @property
    def ollama_models(self) -> tuple[str, ...]:
        return _csv("OLLAMA_MODELS", ",".join(self.models))


settings = Settings()
