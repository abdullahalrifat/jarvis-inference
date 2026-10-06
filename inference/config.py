import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    host: str = os.getenv("INFERENCE_HOST", "0.0.0.0")
    port: int = int(os.getenv("INFERENCE_PORT", "8080"))
    api_key: str = os.getenv("INFERENCE_API_KEY", "")
    max_concurrent_requests: int = int(os.getenv("MAX_CONCURRENT_REQUESTS", "1"))
    max_loaded_models: int = int(os.getenv("MAX_LOADED_MODELS", "1"))
    memory_budget_gb: float = float(os.getenv("MEMORY_BUDGET_GB", "10"))
    memory_headroom_gb: float = float(os.getenv("MEMORY_HEADROOM_GB", "1"))
    default_model: str = os.getenv("DEFAULT_MODEL", "qwen3-1.7b")
    request_timeout_seconds: float = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "600"))
    ollama_url: str = os.getenv("OLLAMA_URL", "http://ollama:11434").rstrip("/")
    llamacpp_url: str = os.getenv("LLAMACPP_URL", "").rstrip("/")

    @property
    def models(self) -> tuple[str, ...]:
        return tuple(x.strip() for x in os.getenv(
            "MODEL_REGISTRY", "qwen3-1.7b,qwen3-4b,qwen3-7b"
        ).split(",") if x.strip())


settings = Settings()
