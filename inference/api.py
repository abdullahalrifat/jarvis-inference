from __future__ import annotations

import base64
import hmac
import json
import struct
import time
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse

from inference.config import settings
from inference.errors import InferenceError
from inference.metrics import render
from inference.models import model_manager
from inference.resources import status as resource_status
from inference.scheduler import scheduler
from inference.schemas import ChatCompletionRequest, EmbeddingRequest, ModelInfo

router = APIRouter()


def _encode_embedding(vector: list[float], encoding_format: str) -> list[float] | str:
    if encoding_format == "float":
        return vector
    packed = struct.pack(f"<{len(vector)}f", *vector)
    return base64.b64encode(packed).decode("ascii")


def _auth(value: str | None) -> None:
    if settings.api_key and not hmac.compare_digest(value or "", settings.api_key):
        raise HTTPException(401, "Invalid inference API key")


def _bearer(value: str | None) -> str | None:
    return value.removeprefix("Bearer ").strip() if value else None


def _request_id(request: Request) -> str:
    return request.headers.get("X-Request-ID") or f"chatcmpl-{uuid.uuid4().hex}"


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "jarvis-inference"}


@router.get("/ready")
async def ready() -> dict[str, object]:
    readiness = await scheduler.readiness()
    if isinstance(readiness, bool):
        readiness = {"ready": readiness}
    body = {
        "status": "ready" if readiness["ready"] else "not_ready",
        "backend": scheduler.backend.name,
        "models": list(settings.models),
        **readiness,
    }
    return JSONResponse(content=body, status_code=200 if readiness["ready"] else 503)


@router.post("/v1/embeddings")
async def embeddings(
    payload: EmbeddingRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    _auth(_bearer(authorization))
    model = payload.model or settings.embedding_model
    inputs = [payload.input] if isinstance(payload.input, str) else payload.input
    try:
        vectors = await scheduler.embeddings(model, inputs)
    except InferenceError as exc:
        raise HTTPException(
            exc.status_code,
            detail={"code": exc.code, "message": exc.message, "retryable": exc.retryable},
        ) from exc
    return {
        "object": "list",
        "data": [
            {"object": "embedding", "embedding": _encode_embedding(vector, payload.encoding_format or "float"), "index": index}
            for index, vector in enumerate(vectors)
        ],
        "model": model,
        "usage": {"prompt_tokens": 0, "total_tokens": 0},
    }


@router.get("/v1/models", response_model=dict)
async def models(authorization: str | None = Header(default=None)) -> dict[str, object]:
    _auth(_bearer(authorization))
    return {
        "object": "list",
        "data": [ModelInfo(id=model).model_dump() for model in settings.models],
    }


@router.get("/v1/inference/status")
async def inference_status(
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    _auth(_bearer(authorization))
    return {"runtime": scheduler.status(), "resources": resource_status()}


@router.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics(
    authorization: str | None = Header(default=None),
) -> PlainTextResponse:
    _auth(_bearer(authorization))
    return PlainTextResponse(render().decode())


@router.post("/v1/chat/completions")
async def chat(
    payload: ChatCompletionRequest,
    request: Request,
    authorization: str | None = Header(default=None),
) -> object:
    _auth(_bearer(authorization))
    request_id = _request_id(request)
    body = payload.model_dump(exclude_none=True)
    body["model"] = body.get("model") or settings.default_model
    try:
        model_manager.validate_chat(str(body["model"]))
    except InferenceError as exc:
        raise HTTPException(
            exc.status_code,
            detail={"code": exc.code, "message": exc.message, "retryable": exc.retryable},
            headers={"X-Request-ID": request_id},
        ) from exc
    if payload.stream:
        return StreamingResponse(
            _stream(body, request_id),
            media_type="text/event-stream",
            headers={
                "X-Request-ID": request_id,
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )
    try:
        result = await scheduler.chat(body)
    except InferenceError as exc:
        raise HTTPException(
            exc.status_code,
            detail={"code": exc.code, "message": exc.message, "retryable": exc.retryable},
            headers={"X-Request-ID": request_id},
        ) from exc
    result.pop("_inference", None)
    result.setdefault("id", request_id)
    result.setdefault("created", int(time.time()))
    result.setdefault("object", "chat.completion")
    result.setdefault("choices", [])
    result.setdefault("usage", {})
    return JSONResponse(content=result, headers={"X-Request-ID": request_id})


async def _stream(body: dict[str, object], request_id: str) -> AsyncIterator[str]:
    model = str(body["model"])
    model_manager.validate_chat(model)
    backend = scheduler.backend
    async for line in scheduler.stream(body):
        if backend.name == "ollama":
            data = backend.sse_data(line)
            message = data.get("message") or {}
            delta: dict[str, object] = {"content": message.get("content", "")}
            if message.get("role"):
                delta["role"] = message["role"]
            if message.get("tool_calls"):
                delta["tool_calls"] = message["tool_calls"]
            chunk = {
                "id": request_id,
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "delta": delta,
                        "finish_reason": data.get("done_reason") if data.get("done") else None,
                    }
                ],
            }
            if data.get("done") and data.get("eval_count") is not None:
                chunk["usage"] = {
                    "prompt_tokens": int(data.get("prompt_eval_count") or 0),
                    "completion_tokens": int(data.get("eval_count") or 0),
                    "total_tokens": int(data.get("prompt_eval_count") or 0)
                    + int(data.get("eval_count") or 0),
                }
            yield f"data: {json.dumps(chunk)}\n\n"
        else:
            yield f"data: {line}\n\n"
    yield "data: [DONE]\n\n"
