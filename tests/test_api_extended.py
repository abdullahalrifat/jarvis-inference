from fastapi.testclient import TestClient

from inference.main import app


def test_ready_returns_backend_state(monkeypatch) -> None:
    async def healthy() -> bool:
        return True

    monkeypatch.setattr("inference.api.scheduler.readiness", healthy)
    response = TestClient(app).get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_metrics_endpoint() -> None:
    response = TestClient(app).get("/metrics")
    assert response.status_code == 200
    assert "inference_requests_total" in response.text


def test_inference_status() -> None:
    response = TestClient(app).get("/v1/inference/status")
    assert response.status_code == 200
    assert "runtime" in response.json()
    assert "resources" in response.json()


def test_request_id_is_preserved(monkeypatch) -> None:
    async def fake_chat(payload):
        return {"model": payload["model"], "choices": [], "usage": {}}

    monkeypatch.setattr("inference.api.scheduler.chat", fake_chat)
    response = TestClient(app).post(
        "/v1/chat/completions",
        headers={"X-Request-ID": "test-request-123"},
        json={"model": "qwen3:1.7b", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert response.status_code == 200
    assert response.json()["id"] == "test-request-123"


def test_default_model_is_used(monkeypatch) -> None:
    async def fake_chat(payload):
        assert payload["model"]
        return {"choices": [], "usage": {}}

    monkeypatch.setattr("inference.api.scheduler.chat", fake_chat)
    response = TestClient(app).post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert response.status_code == 200


def test_invalid_request_is_rejected() -> None:
    response = TestClient(app).post(
        "/v1/chat/completions",
        json={"model": "qwen3:1.7b", "messages": []},
    )
    assert response.status_code == 422
