from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version

from fastapi import FastAPI

from inference.api import router
from inference.config import settings, validate_security_config
from inference.scheduler import scheduler


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
app.include_router(router)
