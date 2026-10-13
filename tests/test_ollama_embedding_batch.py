import pytest

from inference.backends.ollama import OllamaBackend
from inference.errors import InferenceError


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    async def post(self, url, *, json):
        self.calls.append((url, json))
        return FakeResponse(self.payload)

    async def aclose(self):
        return None


@pytest.mark.asyncio
async def test_embeddings_batch_all_inputs_in_one_request():
    client = FakeClient({"embeddings": [[1, 2], [3, 4]]})
    backend = object.__new__(OllamaBackend)
    backend._client = client

    result = await backend.embeddings("nomic-embed-text", ["first", "second"])

    assert result == [[1.0, 2.0], [3.0, 4.0]]
    assert len(client.calls) == 1
    assert client.calls[0][1] == {"model": "nomic-embed-text", "input": ["first", "second"]}
    await backend.close()


@pytest.mark.asyncio
async def test_embeddings_empty_batch_does_not_call_backend():
    client = FakeClient({"embeddings": []})
    backend = object.__new__(OllamaBackend)
    backend._client = client

    assert await backend.embeddings("nomic-embed-text", []) == []
    assert client.calls == []
    await backend.close()


@pytest.mark.asyncio
async def test_embeddings_reject_incomplete_batch():
    client = FakeClient({"embeddings": [[1, 2]]})
    backend = object.__new__(OllamaBackend)
    backend._client = client

    with pytest.raises(InferenceError, match="incomplete embedding batch"):
        await backend.embeddings("nomic-embed-text", ["first", "second"])
    await backend.close()
