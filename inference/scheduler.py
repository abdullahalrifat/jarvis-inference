from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from typing import Any

from inference.backends.llamacpp import LlamaCppBackend
from inference.backends.ollama import OllamaBackend
from inference.config import settings
from inference.errors import InferenceError
from inference.metrics import (
    ACTIVE_MODEL,
    ACTIVE_REQUESTS,
    LATENCY,
    QUEUE,
    QUEUE_WAIT,
    REQUESTS,
    RESOURCE_REJECTIONS,
    TOKENS,
)
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

    def _enqueue(self) -> None:
        try:
            self._queue.put_nowait(object())
        except asyncio.QueueFull as exc:
            raise InferenceError("QUEUE_FULL", "Inference queue is full", True, 429) from exc
        QUEUE.set(self._queue.qsize())

    async def _release(self) -> None:
        await self._queue.get()
        self._queue.task_done()
        QUEUE.set(self._queue.qsize())

    async def chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        model = str(payload.get("model") or settings.default_model)
        model_manager.validate(model)
        self._enqueue()
        enqueued = time.perf_counter()
        try:
            async with self._semaphore:
                QUEUE_WAIT.labels(model=model).observe(time.perf_counter() - enqueued)
                try:
                    admit_request()
                except InferenceError:
                    RESOURCE_REJECTIONS.inc()
                    raise
                model_manager.activate(model)
                ACTIVE_MODEL.labels(model=model).set(1)
                ACTIVE_REQUESTS.inc()
                started = time.perf_counter()
                try:
                    result = await asyncio.wait_for(
                        self.backend.chat(model, payload),
                        timeout=settings.request_timeout_seconds,
                    )
                    usage = result.get("usage", {})
                    TOKENS.labels(model=model, kind="prompt").inc(
                        usage.get("prompt_tokens", 0)
                    )
                    TOKENS.labels(model=model, kind="completion").inc(
                        usage.get("completion_tokens", 0)
                    )
                    REQUESTS.labels(model=model, status="success").inc()
                    return result
                except InferenceError:
                    REQUESTS.labels(model=model, status="error").inc()
                    raise
                except TimeoutError as exc:
                    REQUESTS.labels(model=model, status="error").inc()
                    raise InferenceError(
                        "MODEL_TIMEOUT", "Inference request timed out", True, 504
                    ) from exc
                except Exception as exc:
                    REQUESTS.labels(model=model, status="error").inc()
                    raise InferenceError("INFERENCE_ERROR", str(exc), True, 503) from exc
                finally:
                    ACTIVE_REQUESTS.dec()
                    ACTIVE_MODEL.labels(model=model).set(0)
                    LATENCY.labels(model=model).observe(time.perf_counter() - started)
        finally:
            await self._release()

    async def stream(self, payload: dict[str, Any]) -> AsyncIterator[str]:
        model = str(payload.get("model") or settings.default_model)
        model_manager.validate(model)
        self._enqueue()
        enqueued = time.perf_counter()
        started: float | None = None
        try:
            async with self._semaphore:
                QUEUE_WAIT.labels(model=model).observe(time.perf_counter() - enqueued)
                try:
                    admit_request()
                except InferenceError:
                    RESOURCE_REJECTIONS.inc()
                    raise
                model_manager.activate(model)
                ACTIVE_MODEL.labels(model=model).set(1)
                ACTIVE_REQUESTS.inc()
                started = time.perf_counter()
                try:
                    async with asyncio.timeout(settings.request_timeout_seconds):
                        backend = self.backend
                        async for line in backend.stream(model, payload):
                            yield line
                    REQUESTS.labels(model=model, status="success").inc()
                except InferenceError:
                    REQUESTS.labels(model=model, status="error").inc()
                    raise
                except TimeoutError as exc:
                    REQUESTS.labels(model=model, status="error").inc()
                    raise InferenceError(
                        "MODEL_TIMEOUT", "Inference request timed out", True, 504
                    ) from exc
                except Exception as exc:
                    REQUESTS.labels(model=model, status="error").inc()
                    raise InferenceError("INFERENCE_ERROR", str(exc), True, 503) from exc
                finally:
                    ACTIVE_REQUESTS.dec()
                    ACTIVE_MODEL.labels(model=model).set(0)
                    if started is not None:
                        LATENCY.labels(model=model).observe(time.perf_counter() - started)
        finally:
            await self._release()

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

    async def close(self) -> None:
        await self._ollama.close()
        await self._llama.close()


scheduler = Scheduler()
