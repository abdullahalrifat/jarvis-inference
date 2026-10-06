import httpx
import pytest

from inference.backends.llamacpp import LlamaCppBackend
from inference.backends.ollama import OllamaBackend
from inference.errors import InferenceError


class FakeResponse:
    def __init__(self, data=None, status_code=200, text="") -> None:
        self._data = data or {}
        self.status_code = status_code
        self.text = text

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("POST", "http://test")
            response = httpx.Response(self.status_code, request=request, text=self.text)
            raise httpx.HTTPStatusError("error", request=request, response=response)

    def json(self) -> dict:
        return self._data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def aiter_lines(self):
        for line in ['{"message":{"role":"assistant","content":"hello"}}', '{"done":true}']:
            yield line


class FakeClient:
    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, url):
        return FakeResponse({"models": []})

    async def post(self, url, json):
        return FakeResponse(
            {
                "message": {"role": "assistant", "content": "ok"},
                "prompt_eval_count": 1,
                "eval_count": 2,
            }
        )

    def stream(self, method, url, json):
        return FakeResponse()


@pytest.mark.asyncio
async def test_ollama_health_and_chat(monkeypatch) -> None:
    monkeypatch.setattr("inference.backends.ollama.httpx.AsyncClient", FakeClient)
    backend = OllamaBackend()
    assert await backend.health() is True
    result = await backend.chat("qwen3:1.7b", {"messages": []})
    assert result["usage"]["total_tokens"] == 3


@pytest.mark.asyncio
async def test_ollama_stream(monkeypatch) -> None:
    monkeypatch.setattr("inference.backends.ollama.httpx.AsyncClient", FakeClient)
    lines = [line async for line in OllamaBackend().stream("qwen3:1.7b", {"messages": []})]
    assert len(lines) == 2


@pytest.mark.asyncio
async def test_ollama_timeout_maps_to_inference_error(monkeypatch) -> None:
    class TimeoutClient(FakeClient):
        async def post(self, url, json):
            raise httpx.ReadTimeout("timed out")

    monkeypatch.setattr("inference.backends.ollama.httpx.AsyncClient", TimeoutClient)
    with pytest.raises(InferenceError) as exc:
        await OllamaBackend().chat("qwen3:1.7b", {"messages": []})
    assert exc.value.code == "MODEL_TIMEOUT"


@pytest.mark.asyncio
async def test_llamacpp_unconfigured() -> None:
    backend = LlamaCppBackend()
    with pytest.raises(InferenceError) as exc:
        await backend.chat("qwen3:1.7b", {"messages": []})
    assert exc.value.code == "BACKEND_NOT_CONFIGURED"
