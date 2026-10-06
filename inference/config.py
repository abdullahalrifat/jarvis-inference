from __future__ import annotations

import os
from dataclasses import dataclass, field


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


def _csv(name: str, default: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in os.getenv(name, default).split(",") if item.strip())


@dataclass
class Settings:
    host: str = field(default_factory=lambda: os.getenv("INFERENCE_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: _int("INFERENCE_PORT", 8080))
    api_key: str = field(default_factory=lambda: os.getenv("INFERENCE_API_KEY", ""))
    max_concurrent_requests: int = field(
        default_factory=lambda: max(1, _int("MAX_CONCURRENT_REQUESTS", 1))
    )
    max_queue_size: int = field(default_factory=lambda: max(0, _int("MAX_QUEUE_SIZE", 8)))
    max_loaded_models: int = field(default_factory=lambda: max(1, _int("MAX_LOADED_MODELS", 1)))
    memory_budget_gb: float = field(
        default_factory=lambda: max(0.5, _float("MEMORY_BUDGET_GB", 10.0))
    )
    memory_headroom_gb: float = field(
        default_factory=lambda: max(1.0, _float("MEMORY_HEADROOM_GB", 1.0))
    )
    request_timeout_seconds: float = field(
        default_factory=lambda: max(1.0, _float("REQUEST_TIMEOUT_SECONDS", 600.0))
    )
    shutdown_timeout_seconds: float = field(
        default_factory=lambda: max(1.0, _float("SHUTDOWN_TIMEOUT_SECONDS", 30.0))
    )
    model_refresh_seconds: float = field(
        default_factory=lambda: max(1.0, _float("MODEL_REFRESH_SECONDS", 15.0))
    )
    circuit_failure_threshold: int = field(
        default_factory=lambda: max(1, _int("CIRCUIT_FAILURE_THRESHOLD", 3))
    )
    circuit_recovery_seconds: float = field(
        default_factory=lambda: max(1.0, _float("CIRCUIT_RECOVERY_SECONDS", 15.0))
    )
    default_model: str = field(default_factory=lambda: os.getenv("DEFAULT_MODEL", "qwen3:1.7b"))
    embedding_model: str = field(
        default_factory=lambda: os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
    )
    ollama_url: str = field(
        default_factory=lambda: os.getenv("OLLAMA_URL", "http://ollama:11434").rstrip("/")
    )
    llamacpp_url: str = field(default_factory=lambda: os.getenv("LLAMACPP_URL", "").rstrip("/"))
    ollama_keep_alive: str = field(default_factory=lambda: os.getenv("OLLAMA_KEEP_ALIVE", "30m"))

    @property
    def models(self) -> tuple[str, ...]:
        return _csv("MODEL_REGISTRY", "qwen3:1.7b,qwen3:4b")

    @property
    def inference_models(self) -> tuple[str, ...]:
        return (*self.models, self.embedding_model)

    @property
    def ollama_models(self) -> tuple[str, ...]:
        return _csv("OLLAMA_MODELS", ",".join(self.inference_models))


settings = Settings()
