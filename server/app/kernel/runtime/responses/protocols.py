"""Repository protocols consumed by response services."""

from __future__ import annotations

from typing import Protocol

from app.kernel.runtime.db.models.responses import Response, ResponseEvent


class ResponseRepositoryProtocol(Protocol):
    """Response resource persistence contract."""

    def create(self, response: Response) -> Response: ...

    def update(self, response: Response) -> Response: ...

    def require(self, response_id: str) -> Response: ...

    def list_for_run(self, run_id: str) -> list[Response]: ...


class ResponseEventRepositoryProtocol(Protocol):
    """Response event persistence contract."""

    def create(self, event: ResponseEvent) -> ResponseEvent: ...

    def next_sequence(self, response_id: str) -> int: ...

    def list_for_response(self, response_id: str, *, limit: int, offset: int) -> list[ResponseEvent]: ...

    def list_for_run(self, run_id: str) -> list[ResponseEvent]: ...


__all__ = ["ResponseEventRepositoryProtocol", "ResponseRepositoryProtocol"]
