from dataclasses import dataclass
from threading import Lock

from .config import settings
from .errors import InferenceError


@dataclass(frozen=True)
class ModelSpec:
    id: str


class ModelManager:
    def __init__(self):
        self._lock = Lock()
        self._active: str | None = None

    def validate(self, model: str) -> ModelSpec:
        if model not in settings.models:
            raise InferenceError("UNKNOWN_MODEL", f"Unknown model '{model}'", False, 400)
        return ModelSpec(model)

    def activate(self, model: str) -> None:
        self.validate(model)
        with self._lock:
            self._active = model

    def status(self) -> dict:
        with self._lock:
            return {"active_model": self._active, "max_loaded_models": settings.max_loaded_models}


model_manager = ModelManager()
