import asyncio
from typing import Any
from .backends.llamacpp import LlamaCppBackend
from .backends.ollama import OllamaBackend
from .config import settings
from .errors import InferenceError
from .metrics import metrics
from .models import model_manager
from .resources import admit_request

class Scheduler:
    def __init__(self):
        self._semaphore = asyncio.Semaphore(settings.max_concurrent_requests)
        self._ollama = OllamaBackend()
        self._llama = LlamaCppBackend()

    async def chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        model = payload.get("model") or settings.default_model
        model_manager.validate(model)
        async with self._semaphore:
            admit_request()
            model_manager.activate(model)
            backend = self._llama if settings.llamacpp_url else self._ollama
            try:
                result = await backend.chat(model, payload)
            except Exception:
                metrics.request(model, False)
                raise
            metrics.request(model, True)
            return result

    def status(self) -> dict:
        return {
            **model_manager.status(),
            "queue_limit": settings.max_concurrent_requests,
            "backend": "llama.cpp" if settings.llamacpp_url else "ollama",
        }

scheduler = Scheduler()
