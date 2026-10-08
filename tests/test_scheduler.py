import asyncio

import pytest

from inference.errors import InferenceError
from inference.models import model_manager
from inference.scheduler import Scheduler


class FakeBackend:
    name = "fake"

    async def health(self) -> bool:
        return True

    async def available_models(self) -> list[str]:
        return ["qwen3:1.7b", "qwen3:4b", "nomic-embed-text"]

    async def loaded_models(self) -> list[str]:
        return ["qwen3:1.7b"]

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
    model_manager._available.clear()
    model_manager._loaded.clear()
    model_manager._last_refresh = 0
    return instance


@pytest.mark.asyncio
async def test_chat_success_records_result(scheduler: Scheduler) -> None:
    scheduler._ollama = FakeBackend()
    result = await scheduler.chat({"model": "qwen3:1.7b", "messages": []})

    assert result["model"] == "qwen3:1.7b"
    assert result["usage"] == {"prompt_tokens": 2, "completion_tokens": 3}
    assert scheduler.status()["queue_depth"] == 0
    assert scheduler.status()["warm_requests"] >= 1


@pytest.mark.asyncio
async def test_stream_uses_scheduler_lifecycle(scheduler: Scheduler) -> None:
    scheduler._ollama = FakeBackend()
    chunks = [
        chunk
        async for chunk in scheduler.stream({"model": "qwen3:1.7b", "messages": []})
    ]

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
async def test_resource_pressure_is_normalized(
    monkeypatch, scheduler: Scheduler
) -> None:
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
async def test_readiness_reports_model_availability(scheduler: Scheduler) -> None:
    scheduler._ollama = FakeBackend()
    result = await scheduler.readiness()
    assert result["ready"] is True


@pytest.mark.asyncio
async def test_cancellation_releases_queue_and_active_slot(
    scheduler: Scheduler,
) -> None:
    class BlockingBackend(FakeBackend):
        async def chat(self, model: str, payload: dict) -> dict:
            await asyncio.sleep(10)
            return await super().chat(model, payload)

    scheduler._ollama = BlockingBackend()
    task = asyncio.create_task(scheduler.chat({"model": "qwen3:1.7b", "messages": []}))
    await asyncio.sleep(0.01)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert scheduler.status()["queue_depth"] == 0


@pytest.mark.asyncio
async def test_embedding_resource_pressure_is_counted(
    monkeypatch, scheduler: Scheduler
) -> None:
    scheduler._ollama = FakeBackend()
    monkeypatch.setattr(
        "inference.scheduler.admit_request",
        lambda: (_ for _ in ()).throw(
            InferenceError("RESOURCE_PRESSURE", "not enough memory", True, 503)
        ),
    )

    with pytest.raises(InferenceError) as exc:
        await scheduler.embeddings("nomic-embed-text", ["hello"])

    assert exc.value.code == "RESOURCE_PRESSURE"
    assert scheduler.status()["queue_depth"] == 0


@pytest.mark.asyncio
async def test_readiness_fails_when_model_state_refresh_fails(
    scheduler: Scheduler,
) -> None:
    scheduler._ollama = FakeBackend()

    async def broken_refresh(backend, force=False) -> bool:
        return False

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(model_manager, "refresh", broken_refresh)
    try:
        result = await scheduler.readiness()
    finally:
        monkeypatch.undo()

    assert result == {"ready": False, "reason": "model_state_unavailable"}
