from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from inference.config import settings
from inference.errors import InferenceError


class OllamaBackend:
    name = "ollama"

    def __init__(self) -> None:
        timeout = httpx.Timeout(
            settings.request_timeout_seconds,
            connect=min(10.0, settings.request_timeout_seconds),
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
        try:
            response = await self._client.get(f"{settings.ollama_url}/api/tags", timeout=3)
            response.raise_for_status()
            return True
        except httpx.HTTPError:
            return False

    @staticmethod
    def _canonical_model_name(name: str) -> str:
        """Normalize Ollama's implicit :latest tag to the API model ID."""
        return name[:-len(":latest")] if name.endswith(":latest") else name

    async def available_models(self) -> list[str]:
        response = await self._client.get(f"{settings.ollama_url}/api/tags", timeout=3)
        response.raise_for_status()
        return [
            self._canonical_model_name(str(item["name"]))
            for item in response.json().get("models", [])
        ]

    async def loaded_models(self) -> list[str]:
        response = await self._client.get(f"{settings.ollama_url}/api/ps", timeout=3)
        response.raise_for_status()
        return [
            self._canonical_model_name(str(item["name"]))
            for item in response.json().get("models", [])
        ]

    async def embeddings(self, model: str, inputs: list[str]) -> list[list[float]]:
        try:
            vectors: list[list[float]] = []
            for text in inputs:
                response = await self._client.post(
                    f"{settings.ollama_url}/api/embed",
                    json={"model": model, "input": text},
                )
                response.raise_for_status()
                data = response.json()
                embeddings = data.get("embeddings") or []
                if not embeddings:
                    raise InferenceError("BACKEND_ERROR", "Ollama returned no embedding", True, 503)
                vectors.append([float(value) for value in embeddings[0]])
            return vectors
        except httpx.TimeoutException as exc:
            raise InferenceError(
                "EMBEDDING_TIMEOUT", "Embedding request timed out", True, 504
            ) from exc
        except httpx.HTTPStatusError as exc:
            retryable = exc.response.status_code >= 500
            raise InferenceError(
                "BACKEND_ERROR",
                f"Ollama returned HTTP {exc.response.status_code}: {exc.response.text[:500]}",
                retryable,
                503 if retryable else 400,
            ) from exc
        except InferenceError:
            raise
        except httpx.HTTPError as exc:
            raise InferenceError("BACKEND_UNAVAILABLE", str(exc), True, 503) from exc

    async def chat(self, model: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = await self._client.post(
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
            async with self._client.stream(
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

    @staticmethod
    def _body(model: str, payload: dict[str, Any], stream: bool) -> dict[str, Any]:
        options: dict[str, Any] = {}
        mapping = {
            "max_tokens": "num_predict",
            "temperature": "temperature",
            "top_p": "top_p",
            "top_k": "top_k",
            "seed": "seed",
            "num_ctx": "num_ctx",
            "repeat_penalty": "repeat_penalty",
            "min_p": "min_p",
        }
        for source, target in mapping.items():
            if payload.get(source) is not None:
                options[target] = payload[source]
        body: dict[str, Any] = {
            "model": model,
            "messages": payload.get("messages", []),
            "stream": stream,
            "keep_alive": payload.get("keep_alive") or settings.ollama_keep_alive,
            "options": options,
        }
        if payload.get("stop") is not None:
            options["stop"] = payload["stop"]
        if payload.get("tools") is not None:
            body["tools"] = payload["tools"]
        if payload.get("tool_choice") is not None:
            body["tool_choice"] = payload["tool_choice"]
        response_format = payload.get("response_format")
        if response_format:
            if response_format.get("type") == "json_object":
                body["format"] = "json"
            elif response_format.get("type") == "json_schema":
                body["format"] = response_format.get("json_schema", {}).get("schema")
        return body

    @staticmethod
    def _normalize(model: str, data: dict[str, Any]) -> dict[str, Any]:
        message = data.get("message") or {}
        prompt = int(data.get("prompt_eval_count") or 0)
        completion = int(data.get("eval_count") or 0)
        normalized_message: dict[str, Any] = {
            "role": message.get("role", "assistant"),
            "content": message.get("content", ""),
        }
        if message.get("tool_calls"):
            normalized_message["tool_calls"] = message["tool_calls"]
        inference = {
            "load_seconds": (data.get("load_duration") or 0) / 1e9,
            "generation_seconds": (data.get("eval_duration") or 0) / 1e9,
            "total_seconds": (data.get("total_duration") or 0) / 1e9,
        }
        return {
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": normalized_message,
                    "finish_reason": "tool_calls"
                    if message.get("tool_calls")
                    else data.get("done_reason", "stop"),
                }
            ],
            "usage": {
                "prompt_tokens": prompt,
                "completion_tokens": completion,
                "total_tokens": prompt + completion,
            },
            "_inference": inference,
        }

    @staticmethod
    def sse_data(line: str) -> dict[str, Any]:
        return json.loads(line)
