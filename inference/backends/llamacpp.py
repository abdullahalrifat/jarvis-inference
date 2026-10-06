from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx

from inference.config import settings
from inference.errors import InferenceError


class LlamaCppBackend:
    name = "llama.cpp"

    async def health(self) -> bool:
        if not settings.llamacpp_url:
            return False
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                response = await client.get(f"{settings.llamacpp_url}/health")
                return response.status_code < 500
        except httpx.HTTPError:
            return False

    async def chat(self, model: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not settings.llamacpp_url:
            raise InferenceError(
                "BACKEND_NOT_CONFIGURED", "llama.cpp is not configured", False, 503
            )
        body = dict(payload)
        body["model"] = model
        try:
            async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
                response = await client.post(
                    f"{settings.llamacpp_url}/v1/chat/completions", json=body
                )
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise InferenceError("MODEL_TIMEOUT", "Inference request timed out", True, 504) from exc
        except httpx.HTTPError as exc:
            raise InferenceError("BACKEND_UNAVAILABLE", str(exc), True, 503) from exc
        return response.json()

    async def stream(self, model: str, payload: dict[str, Any]) -> AsyncIterator[str]:
        if not settings.llamacpp_url:
            raise InferenceError(
                "BACKEND_NOT_CONFIGURED", "llama.cpp is not configured", False, 503
            )
        body = dict(payload)
        body["model"] = model
        body["stream"] = True
        try:
            async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
                async with client.stream(
                    "POST", f"{settings.llamacpp_url}/v1/chat/completions", json=body
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            yield line[6:]
        except httpx.TimeoutException as exc:
            raise InferenceError("MODEL_TIMEOUT", "Inference request timed out", True, 504) from exc
        except httpx.HTTPError as exc:
            raise InferenceError("BACKEND_UNAVAILABLE", str(exc), True, 503) from exc
