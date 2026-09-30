"""Request shapes of the Anthropic-compatible surface.

Only what SOIT can honour is modelled, and unknown fields are ignored, the way
Anthropic SDKs expect a compatible server to behave when the SDK is newer than
the server. Message content stays loosely typed: its blocks are checked one by
one in ``convert`` so a refusal can name the block it cannot carry.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

MAX_MESSAGES = 1024


class _Lenient(BaseModel):
    model_config = ConfigDict(extra="ignore")


class MessageIn(_Lenient):
    role: Literal["user", "assistant"]
    content: str | list[dict[str, Any]]


class ToolIn(_Lenient):
    name: str = Field(min_length=1)
    description: str | None = None
    input_schema: dict[str, Any] | None = None
    # ``custom`` or absent for a client-defined tool; anything else names a
    # tool Anthropic runs on its side, which SOIT cannot.
    type: str | None = None


class ToolChoiceIn(_Lenient):
    type: Literal["auto", "any", "tool", "none"]
    name: str | None = None
    disable_parallel_tool_use: bool | None = None


class MessagesRequest(_Lenient):
    model: str = Field(min_length=1)
    max_tokens: int = Field(ge=1)
    messages: list[MessageIn] = Field(min_length=1, max_length=MAX_MESSAGES)
    system: str | list[dict[str, Any]] | None = None
    temperature: float | None = Field(default=None, ge=0, le=1)
    top_p: float | None = Field(default=None, ge=0, le=1)
    stop_sequences: list[str] | None = None
    stream: bool = False
    tools: list[ToolIn] | None = None
    tool_choice: ToolChoiceIn | None = None


class CountTokensRequest(_Lenient):
    model: str = Field(min_length=1)
    messages: list[MessageIn] = Field(min_length=1, max_length=MAX_MESSAGES)
    system: str | list[dict[str, Any]] | None = None
    tools: list[ToolIn] | None = None
