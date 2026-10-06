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

    async def stream(self, model: str, payload: dict):
        yield '{"message":{"role":"assistant","content":"ok"},"done":true}'


class FailingBackend(FakeBackend):
    async def chat(self, model: str, payload: dict) -> dict:
        raise RuntimeError("backend exploded")


class SlowBackend(FakeBackend):
    async def chat(self, model: str, payload: dict) -> dict:
        await asyncio.sleep(0.05)
        return await super().chat(model, payload)


@pytest.fixture
def scheduler() -> Scheduler:
    instance = Scheduler()
    instance._semaphore = asyncio.Semaphore(1)
    instance._queue = asyncio.Queue(maxsize=2)
    return instance


@pytest.mark.asyncio
async def test_chat_success_records_result(scheduler: Scheduler) -> None:
    scheduler._ollama = FakeBackend()
    result = await scheduler.chat({"model": "qwen3:1.7b", "messages": []})

    assert result["model"] == "qwen3:1.7b"
    assert result["usage"] == {"prompt_tokens": 2, "completion_tokens": 3}
    assert scheduler.status()["queue_depth"] == 0


@pytest.mark.asyncio
async def test_stream_uses_scheduler_lifecycle(scheduler: Scheduler) -> None:
    scheduler._ollama = FakeBackend()
    chunks = [chunk async for chunk in scheduler.stream({"model": "qwen3:1.7b", "messages": []})]

    assert chunks
    assert scheduler.status()["queue_depth"] == 0


@pytest.mark.asyncio
async def test_unknown_model_is_rejected(scheduler: Scheduler) -> None:
    with pytest.raises(InferenceError, match="Unknown model") as exc:
        await scheduler.chat({"model": "not-real", "messages": []})

    assert exc.value.code == "UNKNOWN_MODEL"


@pytest.mark.asyncio
async def test_backend_exception_is_normalized(scheduler: Scheduler) -> None:
    scheduler._ollama = FailingBackend()

    with pytest.raises(InferenceError) as exc:
        await scheduler.chat({"model": "qwen3:1.7b", "messages": []})

    assert exc.value.code == "INFERENCE_ERROR"
    assert exc.value.status_code == 503
    assert scheduler.status()["queue_depth"] == 0


@pytest.mark.asyncio
async def test_timeout_is_normalized(monkeypatch, scheduler: Scheduler) -> None:
    scheduler._ollama = SlowBackend()
    monkeypatch.setattr("inference.scheduler.settings.request_timeout_seconds", 0.001)

    with pytest.raises(InferenceError) as exc:
        await scheduler.chat({"model": "qwen3:1.7b", "messages": []})

    assert exc.value.code == "MODEL_TIMEOUT"
    assert exc.value.status_code == 504
    assert scheduler.status()["queue_depth"] == 0


@pytest.mark.asyncio
async def test_queue_full_returns_retryable_error(scheduler: Scheduler) -> None:
    scheduler._queue.put_nowait(object())
    scheduler._queue.put_nowait(object())

    with pytest.raises(InferenceError) as exc:
        await scheduler.chat({"model": "qwen3:1.7b", "messages": []})

    assert exc.value.code == "QUEUE_FULL"
    assert exc.value.retryable is True
    assert exc.value.status_code == 429


@pytest.mark.asyncio
async def test_resource_pressure_is_normalized(monkeypatch, scheduler: Scheduler) -> None:
    scheduler._ollama = FakeBackend()
    monkeypatch.setattr(
        "inference.scheduler.admit_request",
        lambda: (_ for _ in ()).throw(
            InferenceError("RESOURCE_PRESSURE", "not enough memory", True, 503)
        ),
    )

    with pytest.raises(InferenceError) as exc:
        await scheduler.chat({"model": "qwen3:1.7b", "messages": []})

    assert exc.value.code == "RESOURCE_PRESSURE"
    assert scheduler.status()["queue_depth"] == 0


@pytest.mark.asyncio
async def test_readiness_delegates_to_backend(scheduler: Scheduler) -> None:
    scheduler._ollama = FakeBackend()
    assert await scheduler.readiness() is True


def test_status_reports_backend_and_models(scheduler: Scheduler) -> None:
    status = scheduler.status()

    assert status["backend"] == "ollama"
    assert status["queue_depth"] == 0
    assert status["concurrency"] >= 1
    assert "configured_models" in status
