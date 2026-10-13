from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx

from inference.config import settings
from inference.errors import InferenceError


class LlamaCppBackend:
    name = "llama.cpp"

    def __init__(self) -> None:
        timeout = httpx.Timeout(
            settings.backend_http_timeout_seconds,
            connect=min(10.0, settings.backend_http_timeout_seconds),
        )
        limits = httpx.Limits(
            max_connections=2,
            max_keepalive_connections=1,
            keepalive_expiry=30.0,
        )
        self._client = httpx.AsyncClient(timeout=timeout, limits=limits, trust_env=False)

    async def close(self) -> None:
        await self._client.aclose()

    async def health(self) -> bool:
        if not settings.llamacpp_url:
            return False
        try:
            response = await self._client.get(f"{settings.llamacpp_url}/health", timeout=3)
            return 200 <= response.status_code < 300
        except httpx.HTTPError:
            return False

    async def available_models(self) -> list[str]:
        if not settings.llamacpp_url:
            return []
        response = await self._client.get(f"{settings.llamacpp_url}/v1/models", timeout=3)
        response.raise_for_status()
        return [str(item["id"]) for item in response.json().get("data", [])]

    async def loaded_models(self) -> list[str]:
        return []

    async def embeddings(self, model: str, inputs: list[str]) -> list[list[float]]:
        if not settings.llamacpp_url:
            raise InferenceError(
                "BACKEND_NOT_CONFIGURED", "llama.cpp is not configured", False, 503
            )
        try:
            response = await self._client.post(
                f"{settings.llamacpp_url}/v1/embeddings",
                json={"model": model, "input": inputs},
            )
            response.raise_for_status()
            data = response.json()
            return [list(map(float, item["embedding"])) for item in data.get("data", [])]
        except httpx.TimeoutException as exc:
            raise InferenceError(
                "EMBEDDING_TIMEOUT", "Embedding request timed out", True, 504
            ) from exc
        except httpx.HTTPStatusError as exc:
            retryable = exc.response.status_code >= 500
            raise InferenceError(
                "BACKEND_ERROR",
                f"llama.cpp returned HTTP {exc.response.status_code}: {exc.response.text[:500]}",
                retryable,
                503 if retryable else 400,
            ) from exc
        except httpx.HTTPError as exc:
            raise InferenceError("BACKEND_UNAVAILABLE", str(exc), True, 503) from exc

    async def chat(self, model: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not settings.llamacpp_url:
            raise InferenceError(
                "BACKEND_NOT_CONFIGURED", "llama.cpp is not configured", False, 503
            )
        body = dict(payload)
        body["model"] = model
        try:
            response = await self._client.post(
                f"{settings.llamacpp_url}/v1/chat/completions", json=body
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise InferenceError("MODEL_TIMEOUT", "Inference request timed out", True, 504) from exc
        except httpx.HTTPStatusError as exc:
            retryable = exc.response.status_code >= 500
            raise InferenceError(
                "BACKEND_ERROR",
                f"llama.cpp returned HTTP {exc.response.status_code}: {exc.response.text[:500]}",
                retryable,
                503 if retryable else 400,
            ) from exc
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
            async with self._client.stream(
                "POST", f"{settings.llamacpp_url}/v1/chat/completions", json=body
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        yield line[6:]
        except httpx.TimeoutException as exc:
            raise InferenceError("MODEL_TIMEOUT", "Inference request timed out", True, 504) from exc
        except httpx.HTTPStatusError as exc:
            retryable = exc.response.status_code >= 500
            raise InferenceError(
                "BACKEND_ERROR",
                f"llama.cpp returned HTTP {exc.response.status_code}: {exc.response.text[:500]}",
                retryable,
                503 if retryable else 400,
            ) from exc
        except httpx.HTTPError as exc:
            raise InferenceError("BACKEND_UNAVAILABLE", str(exc), True, 503) from exc
