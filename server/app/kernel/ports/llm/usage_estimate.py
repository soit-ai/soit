"""Token estimates for a model call that ends before the provider reports usage.

Providers report a streamed call's usage in its last chunk, so a stream that
ends early (abandoned by its consumer, or failed part way) ends without one,
and some OpenAI-compatible backends never send it at all. The provider still
bills for the prompt and for what it generated; these estimates let that call
land in the ledger instead of costing nothing.

The counts are deliberately simple and provider-neutral: about four ASCII
characters per token, and one token for every other character, which
over-counts non-Latin text slightly rather than under-counting it. Images
count a typical per-image charge, and only visible output is counted, so for
large images and for reasoning a provider does not stream the estimate is a
lower bound. A cost row built from them is flagged as estimated.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable
from dataclasses import asdict, is_dataclass
from typing import Any

from app.kernel.ports.llm.interface import ChatMessage, ToolCall, ToolCallDelta

# Chat formats wrap every message in a few tokens of role and separators.
MESSAGE_OVERHEAD_TOKENS = 4
# A low-detail image, the smallest charge the major providers document.
LOW_DETAIL_IMAGE_TOKENS = 85
# A square image around 1024 pixels at full detail.
IMAGE_TOKENS = 765


def estimate_text_tokens(text: str | None) -> int:
    """Estimate how many tokens `text` takes."""

    if not text:
        return 0
    ascii_chars = sum(1 for char in text if char < "\x80")
    return math.ceil(ascii_chars / 4) + len(text) - ascii_chars


def _json_text(value: Any) -> str:
    if is_dataclass(value) and not isinstance(value, type):
        value = asdict(value)
    return json.dumps(value, default=str, ensure_ascii=False)


def estimate_prompt_tokens(messages: Iterable[ChatMessage], tools: Iterable[Any] | None = None) -> int:
    """Estimate the prompt a chat call sent: messages, images and tool definitions."""

    total = 0
    for message in messages:
        total += MESSAGE_OVERHEAD_TOKENS + estimate_text_tokens(message.content)
        for image in message.images or []:
            total += LOW_DETAIL_IMAGE_TOKENS if image.detail == "low" else IMAGE_TOKENS
        for call in message.tool_calls or []:
            total += estimate_text_tokens(call.name) + estimate_text_tokens(_json_text(call.arguments))
    for tool in tools or []:
        total += estimate_text_tokens(_json_text(tool))
    return total


class GeneratedText:
    """Collects what a stream generated, as the provider sent it."""

    def __init__(self) -> None:
        self._parts: list[str] = []
        self._saw_call_deltas = False
        self._named_calls: set[int] = set()

    def add(
        self,
        *,
        delta: str | None = None,
        reasoning_delta: str | None = None,
        tool_call_deltas: Iterable[ToolCallDelta] | None = None,
        tool_calls: Iterable[ToolCall] | None = None,
    ) -> None:
        for text in (delta, reasoning_delta):
            if text:
                self._parts.append(text)
        for call_delta in tool_call_deltas or []:
            self._saw_call_deltas = True
            # Some providers repeat a call's name on every argument piece.
            if call_delta.name and call_delta.index not in self._named_calls:
                self._named_calls.add(call_delta.index)
                self._parts.append(call_delta.name)
            self._parts.append(call_delta.arguments_delta)
        if self._saw_call_deltas:
            # A provider that streams calls in pieces may also report them
            # whole at the end; the pieces already counted them.
            return
        for call in tool_calls or []:
            self._parts.append(call.name + _json_text(call.arguments))

    def tokens(self) -> int:
        return estimate_text_tokens("".join(self._parts))
