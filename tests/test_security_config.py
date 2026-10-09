import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from inference.api import _auth
from inference.config import settings, validate_security_config
from inference.main import app


def test_startup_fails_closed_without_api_key(monkeypatch):
    monkeypatch.setattr(settings, "api_key", "")
    monkeypatch.setattr(settings, "allow_insecure_no_auth", False)
    with pytest.raises(RuntimeError, match="INFERENCE_API_KEY is required"):
        validate_security_config()


def test_explicit_development_override_allows_missing_key(monkeypatch):
    monkeypatch.setattr(settings, "api_key", "")
    monkeypatch.setattr(settings, "allow_insecure_no_auth", True)
    validate_security_config()
    _auth(None)


def test_missing_key_rejected_by_protected_api_when_not_opted_in(monkeypatch):
    monkeypatch.setattr(settings, "api_key", "")
    monkeypatch.setattr(settings, "allow_insecure_no_auth", False)
    response = TestClient(app).get("/v1/models")
    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]


def test_configured_key_is_required_even_with_dev_override(monkeypatch):
    monkeypatch.setattr(settings, "api_key", "secret")
    monkeypatch.setattr(settings, "allow_insecure_no_auth", True)
    with pytest.raises(HTTPException) as caught:
        _auth(None)
    assert caught.value.status_code == 401
