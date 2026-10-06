import pytest

from inference.backends.llamacpp import LlamaCppBackend


class Response:
    def __init__(self, data: dict) -> None:
        self._data = data
        self.status_code = 200
        self.text = ""

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._data


class Client:
    async def get(self, url: str, timeout: float = 0) -> Response:
        return Response({"data": [{"id": "qwen3:1.7b"}]})


@pytest.mark.asyncio
async def test_llamacpp_models(monkeypatch) -> None:
    monkeypatch.setattr("inference.backends.llamacpp.settings.llamacpp_url", "http://llama")
    backend = LlamaCppBackend()
    backend._client = Client()

    assert await backend.available_models() == ["qwen3:1.7b"]
    assert await backend.loaded_models() == []


@pytest.mark.asyncio
async def test_llamacpp_health_is_false_when_not_configured(monkeypatch) -> None:
    monkeypatch.setattr("inference.backends.llamacpp.settings.llamacpp_url", "")
    backend = LlamaCppBackend()

    assert await backend.health() is False
    await backend.close()
