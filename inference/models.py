from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock
from typing import Any

from .config import settings
from .errors import InferenceError


@dataclass(frozen=True)
class ModelSpec:
    id: str


class ModelManager:
    def __init__(self) -> None:
        self._lock = Lock()
        self._active: str | None = None
        self._available: set[str] = set()
        self._loaded: set[str] = set()
        self._last_refresh = 0.0
        self._last_load: dict[str, float] = {}
        self._last_unload: dict[str, float] = {}
        self._warm_requests = 0
        self._cold_requests = 0

    def validate(self, model: str) -> ModelSpec:
        if model not in settings.inference_models:
            raise InferenceError(
                "UNKNOWN_MODEL",
                f"Unknown model '{model}'. Use one of: {', '.join(settings.models)}",
                False,
                400,
            )
        return ModelSpec(model)

    def validate_chat(self, model: str) -> ModelSpec:
        if model not in settings.models:
            raise InferenceError(
                "UNKNOWN_MODEL",
                f"Unknown chat model '{model}'. Use one of: {', '.join(settings.models)}",
                False,
                400,
            )
        return ModelSpec(model)

    async def refresh(self, backend: Any, force: bool = False) -> bool:
        now = time.monotonic()
        if not force and now - self._last_refresh < settings.model_refresh_seconds:
            return True
        try:
            available = set(await backend.available_models())
            loaded = set(await backend.loaded_models())
        except Exception:
            return False
        with self._lock:
            previously_loaded = self._loaded
            self._available = available
            self._loaded = loaded
            self._last_refresh = now
            for model in loaded - previously_loaded:
                self._last_load[model] = now
            for model in previously_loaded - loaded:
                self._last_unload[model] = now
        return True

    async def ensure_available(self, backend: Any, model: str) -> bool:
        self.validate(model)
        refreshed = await self.refresh(backend)
        if not refreshed:
            raise InferenceError(
                "BACKEND_UNAVAILABLE", "Unable to query backend model state", True, 503
            )
        with self._lock:
            available = model in self._available
        if not available:
            raise InferenceError(
                "MODEL_UNAVAILABLE",
                f"Model '{model}' is configured but not installed on the backend",
                True,
                503,
            )
        with self._lock:
            return model in self._loaded

    def activate(self, model: str, warm: bool) -> None:
        self.validate(model)
        with self._lock:
            self._active = model
            if warm:
                self._warm_requests += 1
            else:
                self._cold_requests += 1

    def record_loaded(self, model: str) -> None:
        now = time.monotonic()
        with self._lock:
            if settings.max_loaded_models <= 1:
                for previous in tuple(self._loaded):
                    if previous != model:
                        self._last_unload[previous] = now
                self._loaded = {model}
            else:
                self._loaded.add(model)
            self._last_load[model] = self._last_load.get(model, now)

    def status(self) -> dict[str, object]:
        with self._lock:
            loaded = sorted(self._loaded)
            return {
                "active_model": self._active,
                "configured_models": list(settings.models),
                "available_models": sorted(self._available),
                "loaded_models": loaded,
                "warm_models": loaded,
                "max_loaded_models": settings.max_loaded_models,
                "warm_requests": self._warm_requests,
                "cold_requests": self._cold_requests,
                "last_refresh_seconds_ago": (
                    round(max(0.0, time.monotonic() - self._last_refresh), 2)
                    if self._last_refresh
                    else None
                ),
            }


model_manager = ModelManager()
