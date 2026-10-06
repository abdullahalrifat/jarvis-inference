from fastapi.testclient import TestClient

from inference.main import app


def test_ready_returns_backend_state(monkeypatch) -> None:
    async def healthy() -> bool:
        return True

    monkeypatch.setattr("inference.api.scheduler.readiness", healthy)
    response = TestClient(app).get("/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_ready_reports_not_ready(monkeypatch) -> None:
    async def unhealthy() -> bool:
        return False

    monkeypatch.setattr("inference.api.scheduler.readiness", unhealthy)
    response = TestClient(app).get("/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"


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
    assert response.headers["X-Request-ID"] == "test-request-123"
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


def test_backend_error_is_returned_as_openai_error(monkeypatch) -> None:
    from inference.errors import InferenceError

    async def fail(payload):
        raise InferenceError("BACKEND_ERROR", "backend unavailable", True, 503)

    monkeypatch.setattr("inference.api.scheduler.chat", fail)
    response = TestClient(app).post(
        "/v1/chat/completions",
        json={"model": "qwen3:1.7b", "messages": [{"role": "user", "content": "hi"}]},
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "BACKEND_ERROR"


def test_models_endpoint_contains_concrete_ids() -> None:
    response = TestClient(app).get("/v1/models")

    assert response.status_code == 200
    assert all(":" in item["id"] for item in response.json()["data"])
