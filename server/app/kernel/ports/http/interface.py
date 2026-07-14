"""Governed HTTP fetch port interface."""

from dataclasses import dataclass
from typing import Protocol

from app.kernel.contracts.context import RequestContext


@dataclass(frozen=True)
class FetchedResource:
    """Bounded HTTP response returned by the governed fetch gateway."""

    content: bytes
    content_type: str
    final_url: str
    status_code: int


class HttpFetchPort(Protocol):
    """Fetch public resources through egress and network safety policies."""

    async def fetch(
        self,
        ctx: RequestContext,
        url: str,
        *,
        max_bytes: int,
    ) -> FetchedResource:
        """Fetch a bounded resource after enforcing all policies."""

