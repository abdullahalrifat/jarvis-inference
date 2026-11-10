from __future__ import annotations

import base64
import hmac
import json
import logging
import struct
import time
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from starlette.background import BackgroundTask

from inference.config import settings
from inference.errors import InferenceError
from inference.metrics import render
from inference.models import model_manager
from inference.resources import status as resource_status
from inference.scheduler import StreamLease, scheduler
from inference.schemas import ChatCompletionRequest, EmbeddingRequest, ModelInfo

router = APIRouter()

logger = logging.getLogger("jarvis.api")

# Parameters tolerated by the request schema (extra="allow") but not
# implemented by this gateway. They are rejected with an explicit
# OpenAI-compatible 400 instead of being silently dropped (GW-11).
UNSUPPORTED_CHAT_PARAMS = frozenset(
    {
        "n",
        "logprobs",
        "top_logprobs",
        "logit_bias",
        "presence_penalty",
        "frequency_penalty",
    }
)


def _error_headers(request_id: str, exc: InferenceError | None = None) -> dict[str, str]:
    headers = {"X-Request-ID": request_id}
    if exc is not None:
        if exc.code == "QUEUE_TIMEOUT":
            headers["Retry-After"] = "5"
        elif exc.code == "QUEUE_FULL":
            headers["Retry-After"] = "2"
    return headers


def _error_response(exc: InferenceError, request_id: str) -> JSONResponse:
    """OpenAI-compatible `{"error": {...}}` envelope (GW-7).

    FastAPI's default `{"detail": ...}` envelope breaks OpenAI-SDK error
    handling, so InferenceError paths return this shape directly.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "retryable": exc.retryable,
                "request_id": request_id,
            }
        },
        headers=_error_headers(request_id, exc),
    )


def _encode_embedding(vector: list[float], encoding_format: str) -> list[float] | str:
    if encoding_format == "float":
        return vector
    packed = struct.pack(f"<{len(vector)}f", *vector)
    return base64.b64encode(packed).decode("ascii")


def _auth(value: str | None) -> None:
    if not settings.api_key:
        if settings.allow_insecure_no_auth:
            return
        raise HTTPException(503, "Inference API authentication is not configured")
    if not hmac.compare_digest(value or "", settings.api_key):
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
    request: Request,
    authorization: str | None = Header(default=None),
) -> JSONResponse:
    _auth(_bearer(authorization))
    request_id = _request_id(request)
    model = payload.model or settings.embedding_model
    inputs = [payload.input] if isinstance(payload.input, str) else payload.input
    try:
        vectors = await scheduler.embeddings(model, inputs, request_id=request_id)
    except InferenceError as exc:
        return _error_response(exc, request_id)
    return JSONResponse(
        content={
            "object": "list",
            "data": [
                {
                    "object": "embedding",
                    "embedding": _encode_embedding(vector, payload.encoding_format or "float"),
                    "index": index,
                }
                for index, vector in enumerate(vectors)
            ],
            "model": model,
            "usage": {"prompt_tokens": 0, "total_tokens": 0},
        },
        headers={"X-Request-ID": request_id},
    )


@router.get("/v1/models", response_model=dict)
async def models(authorization: str | None = Header(default=None)) -> dict[str, object]:
    _auth(_bearer(authorization))
    return {
        "object": "list",
        "data": [ModelInfo(id=model).model_dump() for model in settings.models],
    }


@router.get("/v1/capabilities", response_model=dict)
async def capabilities(
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    """Advertise the inference protocol and model capabilities."""
    _auth(_bearer(authorization))
    chat_models = list(settings.models)
    models = []
    for model in chat_models:
        models.append({"id": model, "capabilities": ["chat", "streaming"]})
    models.append({"id": settings.embedding_model, "capabilities": ["embeddings"]})
    return {
        "protocol": {"current": 1, "min_client": 1, "max_client": 1},
        "service": "jarvis-inference",
        "features": [
            "chat",
            "streaming",
            "embeddings",
            "model_catalog",
            "request_ids",
        ],
        "models": models,
        "limits": {
            "max_concurrent_requests": settings.max_concurrent_requests,
            "max_queue_size": settings.max_queue_size,
            "queue_timeout_seconds": settings.queue_timeout_seconds,
            "chat_timeout_seconds": settings.chat_timeout_seconds,
            "stream_timeout_seconds": settings.stream_timeout_seconds,
            "embedding_timeout_seconds": settings.embedding_timeout_seconds,
        },
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
        return _error_response(exc, request_id)
    # Honest rejection for tolerated-but-unimplemented parameters (GW-11):
    # silently dropping them makes clients believe their settings took effect.
    unsupported = sorted(set(body).intersection(UNSUPPORTED_CHAT_PARAMS))
    if unsupported:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "UNSUPPORTED_PARAMETER",
                    "message": (
                        "parameters not supported by this gateway: " + ", ".join(unsupported)
                    ),
                    "retryable": False,
                    "request_id": request_id,
                }
            },
            headers=_error_headers(request_id),
        )
    if payload.stream:
        try:
            lease = await scheduler.prepare_stream(body, request_id=request_id)
        except InferenceError as exc:
            return _error_response(exc, request_id)
        return StreamingResponse(
            _stream(body, request_id, lease),
            media_type="text/event-stream",
            headers={
                "X-Request-ID": request_id,
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
            background=BackgroundTask(scheduler.release_stream, lease),
        )
    try:
        result = await scheduler.chat(body, request_id=request_id)
    except InferenceError as exc:
        return _error_response(exc, request_id)
    result.pop("_inference", None)
    result.setdefault("id", request_id)
    result.setdefault("created", int(time.time()))
    result.setdefault("object", "chat.completion")
    result.setdefault("choices", [])
    result.setdefault("usage", {})
    return JSONResponse(content=result, headers={"X-Request-ID": request_id})


async def _stream(
    body: dict[str, object], request_id: str, lease: StreamLease
) -> AsyncIterator[str]:
    model = str(body["model"])
    model_manager.validate_chat(model)
    backend = scheduler.backend
    # OpenAI streaming semantics (GW-4a): when the client asks for usage via
    # stream_options.include_usage, the usage object ships in a final
    # usage-only chunk with empty choices — not inside the content chunk.
    stream_options = body.get("stream_options")
    include_usage = bool(isinstance(stream_options, dict) and stream_options.get("include_usage"))
    try:
        stream = await scheduler.stream(body, request_id=request_id, lease=lease)
        async for line in stream:
            if backend.name == "ollama":
                try:
                    data = backend.sse_data(line)
                except (json.JSONDecodeError, TypeError, ValueError) as exc:
                    # A malformed backend line must not abort an otherwise
                    # healthy stream; skip it and keep reading (GW-4a).
                    logger.warning(
                        "skipping malformed backend SSE line (request %s): %s",
                        request_id,
                        exc,
                    )
                    continue
                message = data.get("message") or {}
                delta: dict[str, object] = {"content": message.get("content", "")}
                if message.get("role"):
                    delta["role"] = message["role"]
                if message.get("thinking"):
                    delta["reasoning_content"] = message["thinking"]
                if message.get("tool_calls"):
                    delta["tool_calls"] = message["tool_calls"]
                finish_reason: str | None = None
                usage = None
                if data.get("done"):
                    # Map Ollama's done_reason exactly like the non-streaming
                    # response path, so tool calls finish as tool_calls.
                    finish_reason = (
                        "tool_calls"
                        if message.get("tool_calls")
                        else data.get("done_reason", "stop")
                    )
                    if data.get("eval_count") is not None:
                        usage = {
                            "prompt_tokens": int(data.get("prompt_eval_count") or 0),
                            "completion_tokens": int(data.get("eval_count") or 0),
                            "total_tokens": int(data.get("prompt_eval_count") or 0)
                            + int(data.get("eval_count") or 0),
                        }
                chunk = {
                    "id": request_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": delta,
                            "finish_reason": finish_reason,
                        }
                    ],
                }
                if usage is not None and not include_usage:
                    chunk["usage"] = usage
                yield f"data: {json.dumps(chunk)}\n\n"
                if usage is not None and include_usage:
                    usage_chunk = {
                        "id": request_id,
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": model,
                        "choices": [],
                        "usage": usage,
                    }
                    yield f"data: {json.dumps(usage_chunk)}\n\n"
            else:
                yield f"data: {line}\n\n"
    except InferenceError as exc:
        # Once SSE headers are committed, communicate backend failures as an
        # OpenAI-compatible error event rather than abruptly truncating the stream.
        error_event = {
            "error": {
                "code": exc.code,
                "message": exc.message,
                "retryable": exc.retryable,
                "request_id": request_id,
            }
        }
        yield f"data: {json.dumps(error_event)}\n\n"
        yield "data: [DONE]\n\n"
        return
    yield "data: [DONE]\n\n"
