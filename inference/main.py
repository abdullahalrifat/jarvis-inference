from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from inference.api import router
from inference.config import settings, validate_security_config
from inference.scheduler import scheduler


class BodyLimitMiddleware(BaseHTTPMiddleware):
    """Reject oversized POST bodies before pydantic validation (GW-5).

    Without a cap, one giant `messages` payload could fill the 1-2 GB
    container before any validation ran.
    """

    async def dispatch(self, request: Request, call_next):
        if request.method == "POST" and request.url.path.startswith("/v1/"):
            try:
                length = int(request.headers.get("content-length") or 0)
            except ValueError:
                length = 0
            limit = int(settings.max_request_body_mib * 1024 * 1024)
            if length > limit:
                return JSONResponse(
                    status_code=413,
                    content={
                        "error": {
                            "code": "REQUEST_TOO_LARGE",
                            "message": (
                                f"request body exceeds the "
                                f"{settings.max_request_body_mib:g} MiB limit"
                            ),
                            "retryable": False,
                        }
                    },
                )
        return await call_next(request)


@asynccontextmanager
async def lifespan(_: FastAPI):
    validate_security_config()
    yield
    try:
        await asyncio.wait_for(scheduler.close(), timeout=settings.shutdown_timeout_seconds)
    except TimeoutError:
        pass


def _app_version() -> str:
    """Track the installed package version instead of a hardcoded drift (GW-9)."""
    try:
        return package_version("jarvis-inference")
    except PackageNotFoundError:
        return "0.0.0.dev0"


app = FastAPI(title="Jarvis Inference", version=_app_version(), lifespan=lifespan)
app.add_middleware(BodyLimitMiddleware)
app.include_router(router)
