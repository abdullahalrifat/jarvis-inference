import pytest

from inference.backends.ollama import OllamaBackend


def test_ollama_body_maps_generation_tools_and_schema() -> None:
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
            "tools": [{"type": "function", "function": {"name": "weather"}}],
            "tool_choice": "auto",
            "response_format": {
                "type": "json_schema",
                "json_schema": {"schema": {"type": "object"}},
            },
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
    assert body["tools"][0]["function"]["name"] == "weather"
    assert body["tool_choice"] == "auto"
    assert body["format"] == {"type": "object"}


def test_ollama_json_object_mode() -> None:
    body = OllamaBackend._body(
        "qwen3:1.7b",
        {
            "messages": [{"role": "user", "content": "json"}],
            "response_format": {"type": "json_object"},
        },
        False,
    )
    assert body["format"] == "json"


def test_ollama_normalization() -> None:
    result = OllamaBackend._normalize(
        "qwen3:4b",
        {
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"function": {"name": "weather", "arguments": {"city": "Tokyo"}}}],
            },
            "prompt_eval_count": 3,
            "eval_count": 2,
            "load_duration": 1000000,
            "eval_duration": 2000000,
            "total_duration": 4000000,
            "done_reason": "stop",
        },
    )
    assert result["choices"][0]["message"]["tool_calls"]
    assert result["usage"]["total_tokens"] == 5
    assert result["_inference"]["generation_seconds"] == 0.002


@pytest.mark.asyncio
async def test_backend_close() -> None:
    backend = OllamaBackend()
    await backend.close()
    assert backend._client.is_closed
