import pytest

from inference.config import settings
from inference.errors import InferenceError
from inference.models import ModelManager


def test_unknown_model_is_rejected() -> None:
    with pytest.raises(InferenceError) as exc:
        ModelManager().validate("orchestrator")
    assert exc.value.code == "UNKNOWN_MODEL"


def test_concrete_models_are_accepted() -> None:
    assert ModelManager().validate(settings.models[0]).id == settings.models[0]
