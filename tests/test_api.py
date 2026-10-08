from fastapi.testclient import TestClient

from inference.main import app
from inference.scheduler import scheduler


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
    assert response.json()["detail"]["code"] == "UNKNOWN_MODEL"


def test_models() -> None:
    response = TestClient(app).get("/v1/models")
    assert response.status_code == 200
    assert all(":" in item["id"] for item in response.json()["data"])


def test_success_preserves_request_id(monkeypatch) -> None:
    async def fake_chat(payload: dict) -> dict:
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
    async def fake_embeddings(model: str, inputs: list[str]) -> list[list[float]]:
        assert model == "nomic-embed-text"
        assert inputs == ["hello", "world"]
        return [[0.1, 0.2], [0.3, 0.4]]

    monkeypatch.setattr(scheduler, "embeddings", fake_embeddings)
    response = TestClient(app).post(
        "/v1/embeddings",
        json={"model": "nomic-embed-text", "input": ["hello", "world"]},
    )

    assert response.status_code == 200
    assert response.json()["data"][1]["embedding"] == [0.3, 0.4]


def test_embedding_model_is_rejected_for_chat() -> None:
    response = TestClient(app).post(
        "/v1/chat/completions",
        json={
            "model": "nomic-embed-text",
            "messages": [{"role": "user", "content": "hi"}],
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "UNKNOWN_MODEL"


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
    assert response.json()["detail"]["code"] == "UNKNOWN_MODEL"


def test_embeddings_support_base64_encoding(monkeypatch) -> None:
    async def fake_embeddings(model: str, inputs: list[str]) -> list[list[float]]:
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
