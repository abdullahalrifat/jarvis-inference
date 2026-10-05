from typing import Any
import httpx
from ..config import settings
from ..errors import InferenceError

class LlamaCppBackend:
    name = "llama.cpp"

    async def chat(self, model: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not settings.llamacpp_url:
            raise InferenceError("BACKEND_NOT_CONFIGURED", "llama.cpp backend is not configured", False, 503)
        body = dict(payload)
        body.pop("model", None)
        try:
            async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
                response = await client.post(
                    f"{settings.llamacpp_url}/v1/chat/completions",
                    json={"model": model, **body},
                )
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise InferenceError("MODEL_TIMEOUT", "Inference request timed out", True, 504) from exc
        except httpx.HTTPError as exc:
            raise InferenceError("BACKEND_UNAVAILABLE", str(exc), True, 503) from exc
        return response.json()
