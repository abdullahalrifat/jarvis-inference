from inference.config import Settings


def test_settings_parse_environment(monkeypatch) -> None:
    monkeypatch.setenv("INFERENCE_PORT", "9090")
    monkeypatch.setenv("MAX_CONCURRENT_REQUESTS", "3")
    monkeypatch.setenv("MAX_QUEUE_SIZE", "4")
    monkeypatch.setenv("MODEL_REGISTRY", "qwen3:1.7b, qwen3:4b")
    settings = Settings()
    assert settings.port == 9090
    assert settings.max_concurrent_requests == 3
    assert settings.max_queue_size == 4
    assert settings.models == ("qwen3:1.7b", "qwen3:4b")
    assert settings.ollama_models == settings.models
