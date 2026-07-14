"""Persistence protocols consumed by trace services."""

from __future__ import annotations

from typing import Any, Protocol


class RunQueryRepositoryProtocol(Protocol):
    """Minimal query executor contract used by RunService."""

    def exec(self, statement: Any) -> Any: ...


__all__ = ["RunQueryRepositoryProtocol"]
