import asyncio

import pytest

from inference.models import model_manager
from inference.scheduler import Scheduler


class LoadBackend:
    name = "load"

    def __init__(self) -> None:
        self.active = 0
        self.max_active = 0

    async def health(self) -> bool:
        return True

    async def available_models(self) -> list[str]:
        return ["qwen3:1.7b", "qwen3:4b"]

    async def loaded_models(self) -> list[str]:
        return ["qwen3:1.7b"]

    async def chat(self, model: str, payload: dict) -> dict:
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            await asyncio.sleep(0.01)
            return {
                "model": model,
                "choices": [],
                "usage": {"prompt_tokens": 2, "completion_tokens": 3},
            }
        finally:
            self.active -= 1

    async def stream(self, model: str, payload: dict):
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            yield '{"message":{"role":"assistant","content":"ok"},"done":false}'
            await asyncio.sleep(0.01)
            yield '{"message":{"role":"assistant","content":""},"done":true,"eval_count":1,"eval_duration":1000000}'
        finally:
            self.active -= 1


@pytest.mark.asyncio
async def test_bounded_load_never_exceeds_single_generation_slot() -> None:
    instance = Scheduler()
    backend = LoadBackend()
    instance._ollama = backend
    model_manager._available.clear()
    model_manager._loaded.clear()
    model_manager._last_refresh = 0

    results = await asyncio.gather(
        *(instance.chat({"model": "qwen3:1.7b", "messages": []}) for _ in range(8))
    )

    assert len(results) == 8
    assert backend.max_active == 1
    assert instance.status()["queue_depth"] == 0


@pytest.mark.asyncio
async def test_backend_timeout_is_not_retried_by_gateway() -> None:
    instance = Scheduler()
    backend = LoadBackend()
    calls = 0

    async def timed_out_chat(model: str, payload: dict) -> dict:
        nonlocal calls
        calls += 1
        raise TimeoutError("backend read timeout")

    backend.chat = timed_out_chat
    instance._ollama = backend
    model_manager._available.clear()
    model_manager._loaded.clear()
    model_manager._last_refresh = 0

    with pytest.raises(Exception):
        await instance.chat({"model": "qwen3:1.7b", "messages": []})

    assert calls == 1
