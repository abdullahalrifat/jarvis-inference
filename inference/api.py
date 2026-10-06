import hmac
import time
import uuid

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import PlainTextResponse

from inference.config import settings
from inference.errors import InferenceError
from inference.metrics import metrics
from inference.resources import status as resource_status
from inference.scheduler import scheduler

router = APIRouter()


def _auth(value: str | None) -> None:
    if settings.api_key and not hmac.compare_digest(value or "", settings.api_key):
        raise HTTPException(401, "Invalid inference API key")


def _bearer(value: str | None) -> str | None:
    return value.removeprefix("Bearer ") if value else None


@router.get("/health")
async def health():
    return {"status": "ok", "service": "jarvis-inference"}


@router.get("/v1/models")
async def models(authorization: str | None = Header(default=None)):
    _auth(_bearer(authorization))
    return {"object": "list", "data": [
        {"id": model, "object": "model", "owned_by": "jarvis-inference"}
        for model in settings.models
    ]}


@router.get("/v1/inference/status")
async def inference_status(authorization: str | None = Header(default=None)):
    _auth(_bearer(authorization))
    return {"runtime": scheduler.status(), "resources": resource_status()}


@router.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics():
    return metrics.render()


@router.post("/v1/chat/completions")
async def chat(payload: dict, authorization: str | None = Header(default=None)):
    _auth(_bearer(authorization))
    request_id = f"chatcmpl-{uuid.uuid4().hex}"
    try:
        result = await scheduler.chat(payload)
    except InferenceError as exc:
        raise HTTPException(
            exc.status_code,
            detail={"code": exc.code, "message": exc.message, "retryable": exc.retryable},
            headers={"X-Inference-Request-ID": request_id},
        ) from exc
    result.setdefault("id", request_id)
    result.setdefault("created", int(time.time()))
    result.setdefault("object", "chat.completion")
    result.setdefault("choices", [])
    result.setdefault("usage", {})
    return result
