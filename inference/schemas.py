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
    top_p: float | None = Field(default=None, gt=0, le=1)
    top_k: int | None = Field(default=None, gt=0, le=256)
    min_p: float | None = Field(default=None, ge=0, le=1)
    seed: int | None = None
    num_ctx: int | None = Field(default=None, gt=0, le=32768)
    repeat_penalty: float | None = Field(default=None, gt=0, le=3)
    stop: str | list[str] | None = None
    max_tokens: int | None = Field(default=None, gt=0, le=32768)
    tools: list[dict[str, Any]] | None = None
    tool_choice: Any = None
    response_format: dict[str, Any] | None = None
    stream: bool = False
    keep_alive: str | int | None = None


class ModelInfo(BaseModel):
    id: str
    object: str = "model"
    owned_by: str = "jarvis-inference"
