import pytest
from pydantic import ValidationError

from inference.schemas import ChatCompletionRequest


def test_chat_request_accepts_tool_message() -> None:
    request = ChatCompletionRequest(
        messages=[{"role": "tool", "content": "result"}],
    )
    assert request.stream is False


def test_chat_request_validates_temperature() -> None:
    with pytest.raises(ValidationError):
        ChatCompletionRequest(
            messages=[{"role": "user", "content": "hi"}],
            temperature=3,
        )
