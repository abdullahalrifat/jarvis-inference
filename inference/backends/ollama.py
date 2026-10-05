from typing import Any
import httpx
from ..config import settings
from ..errors import InferenceError

class OllamaBackend:
    name = "ollama"

    async def chat(self, model: str, payload: dict[str, Any]) -> dict[str, Any]:
        options = {}
        if payload.get("max_tokens") is not None:
            options["num_predict"] = payload["max_tokens"]
        if payload.get("temperature") is not None:
            options["temperature"] = payload["temperature"]
        body = {
            "model": model,
            "messages": payload.get("messages", []),
            "stream": False,
            "keep_alive": payload.get("keep_alive", "10m"),
            "options": options,
        }
        try:
            async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
                response = await client.post(f"{settings.ollama_url}/api/chat", json=body)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise InferenceError("MODEL_TIMEOUT", "Inference request timed out", True, 504) from exc
        except httpx.HTTPError as exc:
            raise InferenceError("BACKEND_UNAVAILABLE", str(exc), True, 503) from exc
        data = response.json()
        message = data.get("message", {})
        prompt = data.get("prompt_eval_count", 0)
        completion = data.get("eval_count", 0)
        return {
            "model": model,
            "choices": [{
                "index": 0,
                "message": {"role": message.get("role", "assistant"), "content": message.get("content", "")},
                "finish_reason": "stop",
            }],
            "usage": {
                "prompt_tokens": prompt,
                "completion_tokens": completion,
                "total_tokens": prompt + completion,
            },
        }
