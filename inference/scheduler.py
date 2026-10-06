from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Any

from inference.backends.llamacpp import LlamaCppBackend
from inference.backends.ollama import OllamaBackend
from inference.circuit import CircuitOpenError, CircuitBreaker
from inference.config import settings
from inference.errors import InferenceError
from inference.metrics import (
    ACTIVE_MODEL,
    ACTIVE_REQUESTS,
    BACKEND_ERRORS,
    CIRCUIT_STATE,
    GENERATION_DURATION,
    LATENCY,
    MODEL_LOAD,
    QUEUE,
    QUEUE_WAIT,
    REQUESTS,
    RESOURCE_REJECTIONS,
    TOKENS,
    TOKENS_PER_SECOND,
    TTFT,
)
from inference.models import model_manager
from inference.resources import admit_request


class Scheduler:
    def __init__(self) -> None:
        self._semaphore = asyncio.Semaphore(settings.max_concurrent_requests)
        self._queue = asyncio.Queue(maxsize=settings.max_queue_size)
        self._ollama = OllamaBackend()
        self._llama = LlamaCppBackend()
        self._circuits = {
            "ollama": CircuitBreaker(
                settings.circuit_failure_threshold, settings.circuit_recovery_seconds
            ),
            "llama.cpp": CircuitBreaker(
                settings.circuit_failure_threshold, settings.circuit_recovery_seconds
            ),
        }

    @property
    def backend(self) -> OllamaBackend | LlamaCppBackend:
        return self._llama if settings.llamacpp_url else self._ollama

    @property
    def circuit(self) -> CircuitBreaker:
        if self.backend.name not in self._circuits:
            self._circuits[self.backend.name] = CircuitBreaker(
                settings.circuit_failure_threshold, settings.circuit_recovery_seconds
            )
        return self._circuits[self.backend.name]

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

    def _backend_failure(self, exc: InferenceError) -> None:
        if exc.code in {"BACKEND_ERROR", "BACKEND_UNAVAILABLE", "MODEL_TIMEOUT", "INFERENCE_ERROR"}:
            self.circuit.failure()
            BACKEND_ERRORS.labels(backend=self.backend.name, code=exc.code).inc()
        self._record_circuit()

    def _record_circuit(self) -> None:
        CIRCUIT_STATE.labels(backend=self.backend.name).set(
            1 if self.circuit.status()["state"] == "open" else 0
        )

    def _check_circuit(self) -> None:
        try:
            self.circuit.allow()
        except CircuitOpenError as exc:
            self._record_circuit()
            raise InferenceError(
                "CIRCUIT_OPEN",
                "Inference backend is temporarily unavailable",
                True,
                503,
            ) from exc

    @staticmethod
    def _record_inference_metrics(model: str, data: dict[str, Any]) -> None:
        timing = data.get("_inference") or {}
        load = float(timing.get("load_seconds") or 0)
        generation = float(timing.get("generation_seconds") or 0)
        if load:
            MODEL_LOAD.labels(model=model).observe(load)
        if generation:
            GENERATION_DURATION.labels(model=model).observe(generation)
        completion = int((data.get("usage") or {}).get("completion_tokens") or 0)
        if completion and generation:
            TOKENS_PER_SECOND.labels(model=model).observe(completion / generation)

    async def _prepare(self, model: str) -> bool:
        model_manager.validate(model)
        self._check_circuit()
        return await model_manager.ensure_available(self.backend, model)

    async def chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        model = str(payload.get("model") or settings.default_model)
        warm = await self._prepare(model)
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
                model_manager.activate(model, warm)
                ACTIVE_MODEL.labels(model=model).set(1)
                ACTIVE_REQUESTS.inc()
                started = time.perf_counter()
                try:
                    result = await asyncio.wait_for(
                        self.backend.chat(model, payload),
                        timeout=settings.request_timeout_seconds,
                    )
                    self.circuit.success()
                    self._record_circuit()
                    usage = result.get("usage", {})
                    TOKENS.labels(model=model, kind="prompt").inc(
                        usage.get("prompt_tokens", 0)
                    )
                    TOKENS.labels(model=model, kind="completion").inc(
                        usage.get("completion_tokens", 0)
                    )
                    self._record_inference_metrics(model, result)
                    REQUESTS.labels(model=model, status="success").inc()
                    return result
                except asyncio.CancelledError:
                    raise
                except InferenceError as exc:
                    self._backend_failure(exc)
                    REQUESTS.labels(model=model, status="error").inc()
                    raise
                except TimeoutError as exc:
                    error = InferenceError(
                        "MODEL_TIMEOUT", "Inference request timed out", True, 504
                    )
                    self._backend_failure(error)
                    REQUESTS.labels(model=model, status="error").inc()
                    raise error from exc
                except Exception as exc:
                    error = InferenceError("INFERENCE_ERROR", str(exc), True, 503)
                    self._backend_failure(error)
                    REQUESTS.labels(model=model, status="error").inc()
                    raise error from exc
                finally:
                    ACTIVE_REQUESTS.dec()
                    ACTIVE_MODEL.labels(model=model).set(0)
                    LATENCY.labels(model=model).observe(time.perf_counter() - started)
        finally:
            await self._release()

    async def stream(self, payload: dict[str, Any]) -> AsyncIterator[str]:
        model = str(payload.get("model") or settings.default_model)
        warm = await self._prepare(model)
        self._enqueue()
        enqueued = time.perf_counter()
        started: float | None = None
        first_token: float | None = None
        try:
            async with self._semaphore:
                QUEUE_WAIT.labels(model=model).observe(time.perf_counter() - enqueued)
                try:
                    admit_request()
                except InferenceError:
                    RESOURCE_REJECTIONS.inc()
                    raise
                model_manager.activate(model, warm)
                ACTIVE_MODEL.labels(model=model).set(1)
                ACTIVE_REQUESTS.inc()
                started = time.perf_counter()
                try:
                    async with asyncio.timeout(settings.request_timeout_seconds):
                        async for line in self.backend.stream(model, payload):
                            now = time.perf_counter()
                            if first_token is None:
                                first_token = now
                                TTFT.labels(model=model).observe(now - started)
                            try:
                                event = json.loads(line)
                            except (TypeError, ValueError):
                                event = {}
                            if event.get("done"):
                                load = float(event.get("load_duration") or 0) / 1e9
                                generation = float(event.get("eval_duration") or 0) / 1e9
                                completion = int(event.get("eval_count") or 0)
                                if load:
                                    MODEL_LOAD.labels(model=model).observe(load)
                                if generation:
                                    GENERATION_DURATION.labels(model=model).observe(generation)
                                if completion:
                                    TOKENS.labels(model=model, kind="completion").inc(completion)
                                    if generation:
                                        TOKENS_PER_SECOND.labels(model=model).observe(
                                            completion / generation
                                        )
                            yield line
                    self.circuit.success()
                    self._record_circuit()
                    REQUESTS.labels(model=model, status="success").inc()
                except asyncio.CancelledError:
                    raise
                except InferenceError as exc:
                    self._backend_failure(exc)
                    REQUESTS.labels(model=model, status="error").inc()
                    raise
                except TimeoutError as exc:
                    error = InferenceError(
                        "MODEL_TIMEOUT", "Inference request timed out", True, 504
                    )
                    self._backend_failure(error)
                    REQUESTS.labels(model=model, status="error").inc()
                    raise error from exc
                except Exception as exc:
                    error = InferenceError("INFERENCE_ERROR", str(exc), True, 503)
                    self._backend_failure(error)
                    REQUESTS.labels(model=model, status="error").inc()
                    raise error from exc
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
            "circuit": self.circuit.status(),
            **model_manager.status(),
        }

    async def readiness(self) -> dict[str, Any]:
        backend_ok = await self.backend.health()
        if not backend_ok:
            return {"ready": False, "reason": "backend_unhealthy"}
        await model_manager.refresh(self.backend, force=True)
        state = model_manager.status()
        configured = set(settings.models)
        available = set(state["available_models"])
        missing = sorted(configured - available)
        if missing:
            return {"ready": False, "reason": "models_missing", "missing_models": missing}
        try:
            self._check_circuit()
        except InferenceError:
            return {"ready": False, "reason": "circuit_open"}
        return {"ready": True, "missing_models": []}

    async def close(self) -> None:
        await self._ollama.close()
        await self._llama.close()


scheduler = Scheduler()
