import json

from fastapi.testclient import TestClient

from inference.errors import InferenceError
from inference.main import app
from inference.scheduler import StreamLease, scheduler


def test_openapi_reports_package_version() -> None:
    from importlib.metadata import version

    response = TestClient(app).get("/openapi.json")
    assert response.status_code == 200
    # The gateway must report the installed package version, never a
    # hardcoded constant that drifts from pyproject.toml (GW-9).
    assert response.json()["info"]["version"] == version("jarvis-inference")


def test_health() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_unknown_model() -> None:
    response = TestClient(app).post(
        "/v1/chat/completions",
        json={"model": "not-a-model", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UNKNOWN_MODEL"


def test_models() -> None:
    response = TestClient(app).get("/v1/models")
    assert response.status_code == 200
    assert all(":" in item["id"] for item in response.json()["data"])


def test_success_preserves_request_id(monkeypatch) -> None:
    captured: dict = {}

    async def fake_chat(payload: dict, request_id: str | None = None) -> dict:
        captured["request_id"] = request_id
        return {
            "model": payload["model"],
            "choices": [],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }

    monkeypatch.setattr(scheduler, "chat", fake_chat)
    response = TestClient(app).post(
        "/v1/chat/completions",
        headers={"X-Request-ID": "req-test-123"},
        json={"model": "qwen3:1.7b", "messages": [{"role": "user", "content": "hi"}]},
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req-test-123"
    assert response.json()["id"] == "req-test-123"
    assert captured["request_id"] == "req-test-123"


def test_capabilities_advertise_protocol_and_models() -> None:
    response = TestClient(app).get("/v1/capabilities")
    assert response.status_code == 200
    body = response.json()
    assert body["protocol"]["current"] == 1
    assert "chat" in body["features"]
    assert {
        "id": "nomic-embed-text",
        "capabilities": ["embeddings"],
    } in body["models"]
    assert body["limits"]["queue_timeout_seconds"] > 0


def test_metrics_requires_auth_when_configured(monkeypatch) -> None:
    monkeypatch.setattr("inference.api.settings.api_key", "secret")
    response = TestClient(app).get("/metrics")
    assert response.status_code == 401


def test_readiness_shape(monkeypatch) -> None:
    async def fake_readiness() -> dict:
        return {"ready": True, "missing_models": []}

    monkeypatch.setattr(scheduler, "readiness", fake_readiness)
    response = TestClient(app).get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_readiness_returns_503_when_backend_not_ready(monkeypatch) -> None:
    async def fake_readiness() -> dict:
        return {"ready": False, "reason": "backend_unhealthy"}

    monkeypatch.setattr(scheduler, "readiness", fake_readiness)
    response = TestClient(app).get("/ready")
    assert response.status_code == 503
    assert response.json()["reason"] == "backend_unhealthy"


def test_embeddings(monkeypatch) -> None:
    captured: dict = {}

    async def fake_embeddings(
        model: str, inputs: list[str], request_id: str | None = None
    ) -> list[list[float]]:
        captured["request_id"] = request_id
        assert model == "nomic-embed-text"
        assert inputs == ["hello", "world"]
        return [[0.1, 0.2], [0.3, 0.4]]

    monkeypatch.setattr(scheduler, "embeddings", fake_embeddings)
    response = TestClient(app).post(
        "/v1/embeddings",
        headers={"X-Request-ID": "embed-test-123"},
        json={"model": "nomic-embed-text", "input": ["hello", "world"]},
    )

    assert response.status_code == 200
    assert response.json()["data"][1]["embedding"] == [0.3, 0.4]
    assert captured["request_id"] == "embed-test-123"


def test_embedding_model_is_rejected_for_chat() -> None:
    response = TestClient(app).post(
        "/v1/chat/completions",
        json={
            "model": "nomic-embed-text",
            "messages": [{"role": "user", "content": "hi"}],
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UNKNOWN_MODEL"


def test_invalid_stream_model_is_rejected_before_streaming() -> None:
    response = TestClient(app).post(
        "/v1/chat/completions",
        json={
            "model": "not-a-model",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UNKNOWN_MODEL"


def test_embeddings_support_base64_encoding(monkeypatch) -> None:
    async def fake_embeddings(
        model: str, inputs: list[str], request_id: str | None = None
    ) -> list[list[float]]:
        return [[1.0, -2.5]]

    monkeypatch.setattr(scheduler, "embeddings", fake_embeddings)
    response = TestClient(app).post(
        "/v1/embeddings",
        json={
            "model": "nomic-embed-text",
            "input": "hello",
            "encoding_format": "base64",
        },
    )

    assert response.status_code == 200
    assert response.json()["data"][0]["embedding"] == "AACAPwAAIMA="


def test_queue_timeout_returns_retry_after(monkeypatch) -> None:
    async def timed_out_chat(payload: dict, request_id: str | None = None) -> dict:
        raise InferenceError("QUEUE_TIMEOUT", "queue wait expired", True, 429)

    monkeypatch.setattr(scheduler, "chat", timed_out_chat)
    response = TestClient(app).post(
        "/v1/chat/completions",
        json={"model": "qwen3:1.7b", "messages": [{"role": "user", "content": "hi"}]},
    )

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "5"
    assert response.json()["error"]["code"] == "QUEUE_TIMEOUT"


def test_stream_queue_timeout_returns_retry_after(monkeypatch) -> None:
    async def timed_out_stream(payload: dict, request_id: str | None = None):
        raise InferenceError("QUEUE_TIMEOUT", "queue wait expired", True, 429)

    monkeypatch.setattr(scheduler, "prepare_stream", timed_out_stream)
    response = TestClient(app).post(
        "/v1/chat/completions",
        json={
            "model": "qwen3:1.7b",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        },
    )

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "5"
    assert response.json()["error"]["code"] == "QUEUE_TIMEOUT"


def test_stream_backend_error_is_emitted_as_sse_event(monkeypatch) -> None:
    lease = StreamLease(model="qwen3:1.7b", request_id="stream-request")

    async def prepared_stream(payload: dict, request_id: str | None = None) -> StreamLease:
        return lease

    async def failing_stream(
        payload: dict, request_id: str | None = None, *, lease: StreamLease | None = None
    ):
        async def events():
            raise InferenceError("MODEL_TIMEOUT", "generation timed out", True, 504)
            yield ""

        return events()

    monkeypatch.setattr(scheduler, "prepare_stream", prepared_stream)
    monkeypatch.setattr(scheduler, "stream", failing_stream)
    monkeypatch.setattr(scheduler, "release_stream", lambda _lease: None)
    response = TestClient(app).post(
        "/v1/chat/completions",
        json={
            "model": "qwen3:1.7b",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        },
    )

    assert response.status_code == 200
    assert '"code": "MODEL_TIMEOUT"' in response.text
    assert "data: [DONE]" in response.text


def test_unsupported_parameters_are_rejected() -> None:
    """GW-11: tolerated-but-unimplemented params must 400, not silently drop."""
    response = TestClient(app).post(
        "/v1/chat/completions",
        json={
            "model": "qwen3:1.7b",
            "messages": [{"role": "user", "content": "hi"}],
            "logprobs": True,
            "n": 2,
        },
    )

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "UNSUPPORTED_PARAMETER"
    assert "logprobs" in error["message"]
    assert "n" in error["message"]


def _prepare_stream_stub(monkeypatch, events: list[str]) -> StreamLease:
    lease = StreamLease(model="qwen3:1.7b", request_id="stream-request")

    async def prepared_stream(payload: dict, request_id: str | None = None) -> StreamLease:
        return lease

    async def fake_stream(payload: dict, request_id: str | None = None, *, lease=None):
        async def _events():
            for event in events:
                yield event

        return _events()

    monkeypatch.setattr(scheduler, "prepare_stream", prepared_stream)
    monkeypatch.setattr(scheduler, "stream", fake_stream)
    monkeypatch.setattr(scheduler, "release_stream", lambda _lease: None)
    return lease


_DONE_EVENT = {
    "message": {"role": "assistant", "content": ""},
    "done": True,
    "done_reason": "stop",
    "eval_count": 5,
    "prompt_eval_count": 7,
}


def test_stream_skips_malformed_backend_lines(monkeypatch) -> None:
    """GW-4a: one malformed backend line must not abort a healthy stream."""
    events = [
        '{"message": {"role": "assistant", "content": "hel"}, "done": false}',
        "not-json-at-all",
        '{"message": {"role": "assistant", "content": "lo"}, "done": false}',
        json.dumps(_DONE_EVENT),
    ]
    _prepare_stream_stub(monkeypatch, events)
    response = TestClient(app).post(
        "/v1/chat/completions",
        json={
            "model": "qwen3:1.7b",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        },
    )

    assert response.status_code == 200
    assert "data: [DONE]" in response.text
    chunks = [
        json.loads(line[6:])
        for line in response.text.splitlines()
        if line.startswith("data: ") and not line.endswith("[DONE]")
    ]
    contents = [chunk["choices"][0]["delta"]["content"] for chunk in chunks]
    assert "hel" in contents
    assert "lo" in contents
    finals = [
        chunk["choices"][0]["finish_reason"]
        for chunk in chunks
        if chunk["choices"][0]["finish_reason"]
    ]
    assert finals == ["stop"]


def test_stream_maps_tool_calls_finish_reason(monkeypatch) -> None:
    done = dict(_DONE_EVENT)
    done["done_reason"] = "stop"
    done["message"] = {
        "role": "assistant",
        "content": "",
        "tool_calls": [{"function": {"name": "weather", "arguments": "{}"}}],
    }
    _prepare_stream_stub(monkeypatch, [json.dumps(done)])
    response = TestClient(app).post(
        "/v1/chat/completions",
        json={
            "model": "qwen3:1.7b",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        },
    )

    assert response.status_code == 200
    chunks = [
        json.loads(line[6:])
        for line in response.text.splitlines()
        if line.startswith("data: ") and not line.endswith("[DONE]")
    ]
    finals = [
        chunk["choices"][0]["finish_reason"]
        for chunk in chunks
        if chunk["choices"][0]["finish_reason"]
    ]
    assert finals == ["tool_calls"]


def test_stream_include_usage_emits_usage_only_chunk(monkeypatch) -> None:
    """GW-4a: include_usage ships usage in a final empty-choices chunk."""
    _prepare_stream_stub(monkeypatch, [json.dumps(_DONE_EVENT)])
    response = TestClient(app).post(
        "/v1/chat/completions",
        json={
            "model": "qwen3:1.7b",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
            "stream_options": {"include_usage": True},
        },
    )

    assert response.status_code == 200
    chunks = [
        json.loads(line[6:])
        for line in response.text.splitlines()
        if line.startswith("data: ") and not line.endswith("[DONE]")
    ]
    content_chunks = [chunk for chunk in chunks if chunk["choices"]]
    usage_chunks = [chunk for chunk in chunks if not chunk["choices"]]
    assert len(content_chunks) == 1
    assert "usage" not in content_chunks[0]
    assert len(usage_chunks) == 1
    assert usage_chunks[0]["usage"]["prompt_tokens"] == 7
    assert usage_chunks[0]["usage"]["total_tokens"] == 12


def test_stream_defaults_keep_inline_usage_chunk(monkeypatch) -> None:
    """Without include_usage the tracked usage chunk behavior is unchanged."""
    _prepare_stream_stub(monkeypatch, [json.dumps(_DONE_EVENT)])
    response = TestClient(app).post(
        "/v1/chat/completions",
        json={
            "model": "qwen3:1.7b",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        },
    )

    assert response.status_code == 200
    chunks = [
        json.loads(line[6:])
        for line in response.text.splitlines()
        if line.startswith("data: ") and not line.endswith("[DONE]")
    ]
    final_chunk = chunks[-1]
    assert final_chunk["choices"][0]["finish_reason"] == "stop"
    assert final_chunk["usage"]["total_tokens"] == 12
