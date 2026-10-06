from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="allow")
    role: Literal["system", "user", "assistant", "tool"]
    content: Any


class ChatCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    model: str | None = None
    messages: list[ChatMessage] = Field(min_length=1)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, gt=0, le=32768)
    stream: bool = False
    keep_alive: str | int | None = None


class ModelInfo(BaseModel):
    id: str
    object: str = "model"
    owned_by: str = "jarvis-inference"
