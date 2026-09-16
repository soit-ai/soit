"""Persistence protocols consumed by trace services."""

from __future__ import annotations

from typing import Any, Protocol


class RunQueryRepositoryProtocol(Protocol):
    """Minimal async query executor contract used by RunService."""

    async def exec(self, statement: Any) -> Any: ...

    async def get(self, entity: Any, ident: Any) -> Any: ...


__all__ = ["RunQueryRepositoryProtocol"]
