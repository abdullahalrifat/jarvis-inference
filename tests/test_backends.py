from inference.backends.ollama import OllamaBackend


def test_ollama_body_uses_concrete_model_name() -> None:
    body = OllamaBackend._body(
        "qwen3:4b",
        {"messages": [{"role": "user", "content": "hi"}], "temperature": 0.2},
        False,
    )
    assert body["model"] == "qwen3:4b"
    assert body["options"]["temperature"] == 0.2
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
