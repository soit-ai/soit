"""Read an HTTP response body up to a byte limit.

``response.json()`` and ``response.text`` read the whole body into memory
first, so a tool pointed at a multi-gigabyte URL, or at a server that keeps
streaming, could exhaust the process before anything checked the size.
"""

from __future__ import annotations

import json
from typing import Any

import httpx


class ResponseTooLargeError(Exception):
    """The response body ran past the configured limit."""

    def __init__(self, max_bytes: int) -> None:
        super().__init__(f"Response body exceeds the {max_bytes} byte limit")
        self.max_bytes = max_bytes


async def read_capped(response: httpx.Response, max_bytes: int) -> bytes:
    """Read a streamed response, refusing it once it passes ``max_bytes``."""
    declared = response.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > max_bytes:
        raise ResponseTooLargeError(max_bytes)
    chunks: list[bytes] = []
    size = 0
    async for chunk in response.aiter_bytes():
        size += len(chunk)
        if size > max_bytes:
            raise ResponseTooLargeError(max_bytes)
        chunks.append(chunk)
    return b"".join(chunks)


def decode_body(response: httpx.Response, content: bytes) -> Any:
    """JSON for a JSON response, text otherwise, from an already capped body."""
    if response.headers.get("content-type", "").startswith("application/json"):
        return json.loads(content)
    return content.decode(response.encoding or "utf-8", errors="replace")
