import pytest
from inference.errors import InferenceError
from inference.models import ModelManager

def test_unknown_model_is_rejected():
    with pytest.raises(InferenceError) as exc:
        ModelManager().validate("orchestrator")
    assert exc.value.code == "UNKNOWN_MODEL"

def test_concrete_model_is_accepted():
    assert ModelManager().validate("qwen3-1.7b").id == "qwen3-1.7b"
