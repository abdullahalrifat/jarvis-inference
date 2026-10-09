"""Test-only defaults for exercising unauthenticated local API paths."""
import pytest

from inference.config import settings


@pytest.fixture(autouse=True)
def allow_insecure_test_gateway(monkeypatch):
    # Tests use an in-process gateway. Production startup has no such override.
    monkeypatch.setattr(settings, "allow_insecure_no_auth", True)
