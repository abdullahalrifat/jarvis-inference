from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from inference.config import settings
from inference.errors import InferenceError


class OllamaBackend:
    name = "ollama"

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                response = await client.get(f"{settings.ollama_url}/api/tags")
                response.raise_for_status()
            return True
        except httpx.HTTPError:
            return False

    async def chat(self, model: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
                response = await client.post(
                    f"{settings.ollama_url}/api/chat",
                    json=self._body(model, payload, False),
                )
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise InferenceError("MODEL_TIMEOUT", "Inference request timed out", True, 504) from exc
        except httpx.HTTPStatusError as exc:
            retryable = exc.response.status_code >= 500
            raise InferenceError(
                "BACKEND_ERROR",
                f"Ollama returned HTTP {exc.response.status_code}: {exc.response.text[:500]}",
                retryable,
                503 if retryable else 400,
            ) from exc
        except httpx.HTTPError as exc:
            raise InferenceError("BACKEND_UNAVAILABLE", str(exc), True, 503) from exc
        return self._normalize(model, response.json())

    async def stream(self, model: str, payload: dict[str, Any]) -> AsyncIterator[str]:
        try:
            async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
                async with client.stream(
                    "POST",
                    f"{settings.ollama_url}/api/chat",
                    json=self._body(model, payload, True),
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line:
                            yield line
        except httpx.TimeoutException as exc:
            raise InferenceError("MODEL_TIMEOUT", "Inference request timed out", True, 504) from exc
        except httpx.HTTPError as exc:
            raise InferenceError("BACKEND_UNAVAILABLE", str(exc), True, 503) from exc

    @staticmethod
    def _body(model: str, payload: dict[str, Any], stream: bool) -> dict[str, Any]:
        options: dict[str, Any] = {}
        if payload.get("max_tokens") is not None:
            options["num_predict"] = payload["max_tokens"]
        if payload.get("temperature") is not None:
            options["temperature"] = payload["temperature"]
        return {
            "model": model,
            "messages": payload.get("messages", []),
            "stream": stream,
            "keep_alive": payload.get("keep_alive") or settings.ollama_keep_alive,
            "options": options,
        }

    @staticmethod
    def _normalize(model: str, data: dict[str, Any]) -> dict[str, Any]:
        message = data.get("message") or {}
        prompt = int(data.get("prompt_eval_count") or 0)
        completion = int(data.get("eval_count") or 0)
        return {
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": message.get("role", "assistant"),
                        "content": message.get("content", ""),
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": prompt,
                "completion_tokens": completion,
                "total_tokens": prompt + completion,
            },
        }

    @staticmethod
    def sse_data(line: str) -> dict[str, Any]:
        return json.loads(line)
