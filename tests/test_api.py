from fastapi.testclient import TestClient

from inference.main import app


def test_health() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_unknown_model() -> None:
    response = TestClient(app).post(
        "/v1/chat/completions",
        json={"model": "orchestrator", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "UNKNOWN_MODEL"


def test_models() -> None:
    response = TestClient(app).get("/v1/models")
    assert response.status_code == 200
    assert all(":" in item["id"] for item in response.json()["data"])
