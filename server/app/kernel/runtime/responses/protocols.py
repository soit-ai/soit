"""Repository protocols consumed by response services."""

from __future__ import annotations

from typing import Protocol

from app.kernel.runtime.db.models.responses import Response, ResponseEvent


class ResponseRepositoryProtocol(Protocol):
    """Response resource persistence contract."""

    async def create(self, response: Response) -> Response: ...

    async def update(self, response: Response) -> Response: ...

    async def require(self, response_id: str) -> Response: ...

    async def list_for_run(self, run_id: str) -> list[Response]: ...


class ResponseEventRepositoryProtocol(Protocol):
    """Response event persistence contract."""

    async def create(self, event: ResponseEvent) -> ResponseEvent: ...

    async def next_sequence(self, response_id: str) -> int: ...

    async def list_for_response(
        self,
        response_id: str,
        *,
        limit: int,
        offset: int,
        after_sequence: int | None = None,
    ) -> list[ResponseEvent]: ...

    async def list_for_run(self, run_id: str) -> list[ResponseEvent]: ...


__all__ = ["ResponseEventRepositoryProtocol", "ResponseRepositoryProtocol"]
