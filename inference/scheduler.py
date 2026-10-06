from __future__ import annotations

import asyncio
import time
from typing import Any

from inference.backends.llamacpp import LlamaCppBackend
from inference.backends.ollama import OllamaBackend
from inference.config import settings
from inference.errors import InferenceError
from inference.metrics import ACTIVE_MODEL, LATENCY, QUEUE, REQUESTS, RESOURCE_REJECTIONS, TOKENS
from inference.models import model_manager
from inference.resources import admit_request


class Scheduler:
    def __init__(self) -> None:
        self._semaphore = asyncio.Semaphore(settings.max_concurrent_requests)
        self._queue = asyncio.Queue(maxsize=settings.max_queue_size)
        self._ollama = OllamaBackend()
        self._llama = LlamaCppBackend()

    @property
    def backend(self) -> OllamaBackend | LlamaCppBackend:
        return self._llama if settings.llamacpp_url else self._ollama

    async def chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        model = payload.get("model") or settings.default_model
        model_manager.validate(model)
        if self._queue.full():
            raise InferenceError("QUEUE_FULL", "Inference queue is full", True, 429)
        await self._queue.put(object())
        QUEUE.set(self._queue.qsize())
        started = time.perf_counter()
        try:
            async with self._semaphore:
                try:
                    admit_request()
                except InferenceError:
                    RESOURCE_REJECTIONS.inc()
                    raise
                model_manager.activate(model)
                ACTIVE_MODEL.labels(model=model).set(1)
                result = await asyncio.wait_for(
                    self.backend.chat(model, payload),
                    timeout=settings.request_timeout_seconds,
                )
                usage = result.get("usage", {})
                TOKENS.labels(model=model, kind="prompt").inc(usage.get("prompt_tokens", 0))
                TOKENS.labels(model=model, kind="completion").inc(usage.get("completion_tokens", 0))
                REQUESTS.labels(model=model, status="success").inc()
                return result
        except InferenceError:
            REQUESTS.labels(model=model, status="error").inc()
            raise
        except TimeoutError as exc:
            REQUESTS.labels(model=model, status="error").inc()
            raise InferenceError("MODEL_TIMEOUT", "Inference request timed out", True, 504) from exc
        except Exception as exc:
            REQUESTS.labels(model=model, status="error").inc()
            raise InferenceError("INFERENCE_ERROR", str(exc), True, 503) from exc
        finally:
            ACTIVE_MODEL.labels(model=model).set(0)
            LATENCY.labels(model=model).observe(time.perf_counter() - started)
            await self._queue.get()
            self._queue.task_done()
            QUEUE.set(self._queue.qsize())

    def status(self) -> dict[str, Any]:
        return {
            "queue_depth": self._queue.qsize(),
            "queue_limit": settings.max_queue_size,
            "concurrency": settings.max_concurrent_requests,
            "backend": self.backend.name,
            **model_manager.status(),
        }

    async def readiness(self) -> bool:
        return await self.backend.health()


scheduler = Scheduler()
