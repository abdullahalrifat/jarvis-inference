import pytest

from inference.backends.ollama import OllamaBackend


def test_ollama_body_uses_concrete_model_name() -> None:
    body = OllamaBackend._body(
        "qwen3:4b",
        {
            "messages": [{"role": "user", "content": "hi"}],
            "temperature": 0.2,
            "top_p": 0.9,
            "top_k": 40,
            "seed": 7,
            "num_ctx": 4096,
            "repeat_penalty": 1.1,
            "stop": ["END"],
        },
        False,
    )
    assert body["model"] == "qwen3:4b"
    assert body["options"]["temperature"] == 0.2
    assert body["options"]["top_p"] == 0.9
    assert body["options"]["top_k"] == 40
    assert body["options"]["seed"] == 7
    assert body["options"]["num_ctx"] == 4096
    assert body["options"]["repeat_penalty"] == 1.1
    assert body["options"]["stop"] == ["END"]
    assert body["stream"] is False


def test_ollama_normalization() -> None:
    result = OllamaBackend._normalize(
        "qwen3:4b",
        {
            "message": {"role": "assistant", "content": "ok"},
            "prompt_eval_count": 3,
            "eval_count": 2,
        },
    )
    assert result["choices"][0]["message"]["content"] == "ok"
    assert result["usage"]["total_tokens"] == 5


@pytest.mark.asyncio
async def test_backend_close() -> None:
    backend = OllamaBackend()
    await backend.close()
    assert backend._client.is_closed
