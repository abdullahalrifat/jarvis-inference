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
    assert settings.inference_models == ("qwen3:1.7b", "qwen3:4b", "nomic-embed-text")
    assert settings.ollama_models == settings.inference_models


def test_settings_enforce_safe_minimums(monkeypatch) -> None:
    monkeypatch.setenv("MAX_CONCURRENT_REQUESTS", "0")
    monkeypatch.setenv("MAX_QUEUE_SIZE", "-1")
    monkeypatch.setenv("MAX_LOADED_MODELS", "0")
    monkeypatch.setenv("MEMORY_BUDGET_GB", "0.1")
    monkeypatch.setenv("MEMORY_HEADROOM_GB", "0.1")
    monkeypatch.setenv("REQUEST_TIMEOUT_SECONDS", "0.1")
    monkeypatch.setenv("SHUTDOWN_TIMEOUT_SECONDS", "0.1")

    settings = Settings()

    assert settings.max_concurrent_requests == 1
    assert settings.max_queue_size == 0
    assert settings.max_loaded_models == 1
    assert settings.memory_budget_gb == 0.5
    assert settings.memory_headroom_gb == 1.0
    assert settings.request_timeout_seconds == 1
    assert settings.shutdown_timeout_seconds == 1
