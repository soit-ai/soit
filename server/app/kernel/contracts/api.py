"""Transport-neutral API envelope and pagination contracts."""

from __future__ import annotations

from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, Field

from app.kernel.contracts.pagination import PageToken

T = TypeVar("T")


class ApiEnvelope(BaseModel, Generic[T]):
    """Successful API response shape applied by response middleware."""

    success: Literal[True] = True
    code: str = "OK"
    message: str = "OK"
    data: T
    request_id: str | None = None
    run_id: str | None = None


class ApiErrorEnvelope(BaseModel):
    """Failed API response shape emitted by exception handlers."""

    success: Literal[False] = False
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = None
    run_id: str | None = None


class PaginatedResponse(BaseModel, Generic[T]):
    """Stable cursor pagination response used by public APIs."""

    items: list[T]
    next_page_token: str | None = None
    page_size: int

    @classmethod
    def create(
        cls,
        items: list[T],
        page_size: int,
        has_next: bool = False,
        next_offset: int | None = None,
    ) -> PaginatedResponse[T]:
        next_token = None
        if has_next and next_offset is not None:
            next_token = PageToken(offset=next_offset, limit=page_size).to_string()
        return cls(
            items=items,
            next_page_token=next_token,
            page_size=len(items),
        )
