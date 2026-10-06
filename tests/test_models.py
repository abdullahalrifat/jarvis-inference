import pytest

from inference.config import settings
from inference.errors import InferenceError
from inference.models import ModelManager


def test_unknown_model_is_rejected() -> None:
    with pytest.raises(InferenceError) as exc:
        ModelManager().validate("orchestrator")

    assert exc.value.code == "UNKNOWN_MODEL"
    assert exc.value.status_code == 400


def test_concrete_models_are_accepted() -> None:
    manager = ModelManager()
    spec = manager.validate(settings.models[0])

    assert spec.id == settings.models[0]


def test_activate_and_status() -> None:
    manager = ModelManager()
    model = settings.models[0]

    manager.activate(model)
    status = manager.status()

    assert status["active_model"] == model
    assert model in status["configured_models"]
    assert status["max_loaded_models"] >= 1
