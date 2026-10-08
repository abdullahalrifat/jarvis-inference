from types import SimpleNamespace

from inference.errors import InferenceError
from inference.resources import _read_int, memory_available_gb, memory_limit_bytes


def test_read_int_handles_missing_and_invalid(tmp_path) -> None:
    missing = _read_int(tmp_path / "missing")
    invalid_path = tmp_path / "invalid"
    invalid_path.write_text("not-an-int")
    invalid = _read_int(invalid_path)
    assert missing is None
    assert invalid is None


def test_memory_limit_bytes_parses_cgroup_file(monkeypatch, tmp_path) -> None:
    paths = [tmp_path / "memory.max", tmp_path / "legacy"]
    paths[0].write_text(str(4 * 1024**3))
    paths[1].write_text(str(8 * 1024**3))
    monkeypatch.setattr(
        "inference.resources.Path",
        lambda value: paths[0] if str(value).endswith("memory.max") else paths[1],
    )
    assert memory_limit_bytes() == 4 * 1024**3


def test_memory_admission_uses_host_not_gateway_cgroup(monkeypatch) -> None:
    monkeypatch.setattr(
        "inference.resources.psutil",
        SimpleNamespace(
            virtual_memory=lambda: SimpleNamespace(available=10 * 1024**3),
        ),
    )
    monkeypatch.setattr("inference.resources.settings.memory_budget_gb", 10.0)
    assert memory_available_gb() == 10.0


def test_memory_admission_is_bounded_by_configured_budget(monkeypatch) -> None:
    monkeypatch.setattr(
        "inference.resources.psutil",
        SimpleNamespace(
            virtual_memory=lambda: SimpleNamespace(available=20 * 1024**3),
        ),
    )
    monkeypatch.setattr("inference.resources.settings.memory_budget_gb", 10.0)
    assert memory_available_gb() == 10.0


def test_inference_error_fields() -> None:
    error = InferenceError("CODE", "message", True, 429)
    assert str(error) == "message"
    assert error.code == "CODE"
    assert error.retryable is True
    assert error.status_code == 429
