from inference.config import settings


def test_optiplex_defaults() -> None:
    assert settings.max_concurrent_requests == 1
    assert settings.max_loaded_models == 1
    assert settings.memory_headroom_gb >= 1
    assert ":" in settings.default_model
