import asyncio

import pytest

from inference.errors import InferenceError
from inference.scheduler import Scheduler


class FakeBackend:
    name = "fake"

    async def health(self) -> bool:
        return True

    async def chat(self, model: str, payload: dict) -> dict:
        return {
            "model": model,
            "choices": [],
            "usage": {"prompt_tokens": 2, "completion_tokens": 3},
        }


class FailingBackend(FakeBackend):
    async def chat(self, model: str, payload: dict) -> dict:
        raise RuntimeError("backend exploded")


class SlowBackend(FakeBackend):
    async def chat(self, model: str, payload: dict) -> dict:
        await asyncio.sleep(0.05)
        return await super().chat(model, payload)


@pytest.mark.asyncio
async def test_scheduler_chat_success(monkeypatch) -> None:
    scheduler = Scheduler()
    scheduler._ollama = FakeBackend()
    monkeypatch.setattr(
        "inference.scheduler.settings",
        type(
            "S",
            (),
            {
                "request_timeout_seconds": 1,
                "default_model": "qwen3:1.7b",
                "llamacpp_url": "",
                "models": ("qwen3:1.7b",),
                "max_concurrent_requests": 1,
                "max_queue_size": 2,
            },
        )(),
    )
    scheduler._semaphore = asyncio.Semaphore(1)
    scheduler._queue = asyncio.Queue(maxsize=2)

    result = await scheduler.chat(
        {"model": "qwen3:1.7b", "messages": [{"role": "user", "content": "hi"}]}
    )

    assert result["usage"]["total_tokens"] == 0
    assert scheduler.status()["queue_depth"] == 0


@pytest.mark.asyncio
async def test_scheduler_unknown_model() -> None:
    scheduler = Scheduler()
    with pytest.raises(InferenceError) as exc:
        await scheduler.chat({"model": "not-real", "messages": []})
    assert exc.value.code == "UNKNOWN_MODEL"


@pytest.mark.asyncio
async def test_scheduler_backend_failure() -> None:
    scheduler = Scheduler()
    scheduler._ollama = FailingBackend()
    with pytest.raises(InferenceError) as exc:
        await scheduler.chat({"model": "qwen3:1.7b", "messages": []})
    assert exc.value.code == "INFERENCE_ERROR"
    assert scheduler.status()["queue_depth"] == 0


@pytest.mark.asyncio
async def test_scheduler_timeout(monkeypatch) -> None:
    scheduler = Scheduler()
    scheduler._ollama = SlowBackend()
    monkeypatch.setattr(
        "inference.scheduler.settings",
        type(
            "S",
            (),
            {
                "request_timeout_seconds": 0.001,
                "default_model": "qwen3:1.7b",
                "llamacpp_url": "",
                "models": ("qwen3:1.7b",),
                "max_concurrent_requests": 1,
                "max_queue_size": 2,
            },
        )(),
    )
    scheduler._semaphore = asyncio.Semaphore(1)
    scheduler._queue = asyncio.Queue(maxsize=2)

    with pytest.raises(InferenceError) as exc:
        await scheduler.chat({"model": "qwen3:1.7b", "messages": []})
    assert exc.value.code == "MODEL_TIMEOUT"


@pytest.mark.asyncio
async def test_scheduler_readiness() -> None:
    scheduler = Scheduler()
    scheduler._ollama = FakeBackend()
    assert await scheduler.readiness() is True
