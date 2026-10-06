from fastapi.testclient import TestClient

from inference.main import app
from inference.scheduler import scheduler


def test_tools_and_structured_output_are_openai_compatible(monkeypatch) -> None:
    captured: dict = {}

    async def fake_chat(payload: dict) -> dict:
        captured.update(payload)
        return {
            "model": payload["model"],
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "get_weather",
                                    "arguments": "{\"city\":\"Tokyo\"}",
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5},
            "_inference": {"generation_seconds": 0.01},
        }

    monkeypatch.setattr(scheduler, "chat", fake_chat)
    payload = {
        "model": "qwen3:1.7b",
        "messages": [{"role": "user", "content": "weather?"}],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "parameters": {
                        "type": "object",
                        "properties": {"city": {"type": "string"}},
                    },
                },
            }
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "answer",
                "schema": {"type": "object", "properties": {"answer": {"type": "string"}}},
            },
        },
    }
    response = TestClient(app).post("/v1/chat/completions", json=payload)

    assert response.status_code == 200
    assert captured["tools"][0]["function"]["name"] == "get_weather"
    assert captured["response_format"]["type"] == "json_schema"
    assert "_inference" not in response.json()
    assert response.json()["choices"][0]["message"]["tool_calls"]
