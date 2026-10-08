from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from inference.api import router
from inference.config import settings
from inference.scheduler import scheduler


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    try:
        await asyncio.wait_for(
            scheduler.close(), timeout=settings.shutdown_timeout_seconds
        )
    except TimeoutError:
        pass


app = FastAPI(title="Jarvis Inference", version="0.3.0", lifespan=lifespan)
app.include_router(router)
