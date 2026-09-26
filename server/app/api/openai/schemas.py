"""Request shapes of the OpenAI-compatible surface.

Only what SOIT can honour is modelled; unknown fields are ignored rather than
rejected, the way OpenAI SDKs expect a compatible server to behave when the
SDK is newer than the server.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_MESSAGES = 1024
MAX_EMBEDDING_ITEMS = 256
MAX_EMBEDDING_ITEM_CHARS = 8192


class _Lenient(BaseModel):
    model_config = ConfigDict(extra="ignore")


class ImageUrl(_Lenient):
    url: str = Field(min_length=1)
    detail: str | None = None


class ContentPart(_Lenient):
    type: str
    text: str | None = None
    image_url: ImageUrl | None = None


class FunctionCall(_Lenient):
    name: str
    arguments: str = ""


class MessageToolCall(_Lenient):
    id: str
    type: str = "function"
    function: FunctionCall


class ChatMessageIn(_Lenient):
    role: Literal["system", "developer", "user", "assistant", "tool"]
    content: str | list[ContentPart] | None = None
    name: str | None = None
    tool_calls: list[MessageToolCall] | None = None
    tool_call_id: str | None = None


class FunctionDefinition(_Lenient):
    name: str = Field(min_length=1)
    description: str | None = None
    parameters: dict[str, Any] | None = None


class ToolIn(_Lenient):
    type: Literal["function"] = "function"
    function: FunctionDefinition


class StreamOptions(_Lenient):
    include_usage: bool = False


class ChatCompletionRequest(_Lenient):
    model: str = Field(min_length=1)
    messages: list[ChatMessageIn] = Field(min_length=1, max_length=MAX_MESSAGES)
    temperature: float | None = Field(default=None, ge=0, le=2)
    top_p: float | None = Field(default=None, ge=0, le=1)
    max_tokens: int | None = Field(default=None, ge=1)
    max_completion_tokens: int | None = Field(default=None, ge=1)
    stream: bool = False
    stream_options: StreamOptions | None = None
    tools: list[ToolIn] | None = None
    tool_choice: str | dict[str, Any] | None = None
    response_format: dict[str, Any] | None = None
    stop: str | list[str] | None = None
    seed: int | None = None
    n: int = Field(default=1, ge=1)
    user: str | None = None

    @field_validator("n")
    @classmethod
    def _single_choice(cls, value: int) -> int:
        # Every choice is a separately governed model call; the gateway runs
        # one per request so each one has its own run, budget check and cost.
        if value != 1:
            raise ValueError("n must be 1")
        return value


class EmbeddingRequest(_Lenient):
    model: str = Field(min_length=1)
    input: str | list[str]
    encoding_format: Literal["float", "base64"] = "float"
    dimensions: int | None = Field(default=None, ge=1)
    user: str | None = None

    @field_validator("input")
    @classmethod
    def _bounded_input(cls, value: str | list[str]) -> str | list[str]:
        items = [value] if isinstance(value, str) else value
        if not items:
            raise ValueError("input must not be empty")
        if len(items) > MAX_EMBEDDING_ITEMS:
            raise ValueError(f"input must contain at most {MAX_EMBEDDING_ITEMS} items")
        for item in items:
            if not item.strip():
                raise ValueError("input items must not be blank")
            if len(item) > MAX_EMBEDDING_ITEM_CHARS:
                raise ValueError(
                    f"input items must be at most {MAX_EMBEDDING_ITEM_CHARS} characters"
                )
        return value


class ImageGenerationRequest(_Lenient):
    model: str = Field(min_length=1)
    prompt: str = Field(min_length=1, max_length=32000)
    n: int = Field(default=1, ge=1, le=4)
    size: str | None = None
    response_format: Literal["b64_json", "url"] = "b64_json"
    user: str | None = None
