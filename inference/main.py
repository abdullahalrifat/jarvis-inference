from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from inference.api import router
from inference.scheduler import scheduler


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await scheduler.close()


app = FastAPI(title="Jarvis Inference", version="0.2.0", lifespan=lifespan)
app.include_router(router)
