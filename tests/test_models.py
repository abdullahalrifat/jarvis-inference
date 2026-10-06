import pytest

from inference.errors import InferenceError
from inference.models import ModelManager


class Backend:
    async def available_models(self) -> list[str]:
        return ["qwen3:1.7b", "qwen3:4b"]

    async def loaded_models(self) -> list[str]:
        return ["qwen3:1.7b"]


class LimitedBackend:
    async def available_models(self) -> list[str]:
        return ["qwen3:1.7b"]

    async def loaded_models(self) -> list[str]:
        return []


class BrokenBackend:
    async def available_models(self) -> list[str]:
        raise RuntimeError("offline")

    async def loaded_models(self) -> list[str]:
        return []


@pytest.mark.asyncio
async def test_model_manager_tracks_warm_and_cold_requests() -> None:
    manager = ModelManager()
    warm = await manager.ensure_available(Backend(), "qwen3:1.7b")
    cold = await manager.ensure_available(Backend(), "qwen3:4b")
    manager.activate("qwen3:1.7b", warm)
    manager.activate("qwen3:4b", cold)
    manager.record_loaded("qwen3:4b")

    state = manager.status()
    assert warm is True
    assert cold is False
    assert state["loaded_models"] == ["qwen3:4b"]
    assert state["warm_requests"] == 1
    assert state["cold_requests"] == 1


@pytest.mark.asyncio
async def test_model_manager_rejects_missing_model() -> None:
    manager = ModelManager()
    with pytest.raises(InferenceError) as exc:
        await manager.ensure_available(LimitedBackend(), "qwen3:4b")

    assert exc.value.code == "MODEL_UNAVAILABLE"


@pytest.mark.asyncio
async def test_model_manager_reports_backend_failure() -> None:
    manager = ModelManager()
    with pytest.raises(InferenceError) as exc:
        await manager.ensure_available(BrokenBackend(), "qwen3:1.7b")

    assert exc.value.code == "BACKEND_UNAVAILABLE"


def test_model_manager_rejects_unknown_model() -> None:
    manager = ModelManager()
    with pytest.raises(InferenceError) as exc:
        manager.validate("not-a-model")

    assert exc.value.code == "UNKNOWN_MODEL"
