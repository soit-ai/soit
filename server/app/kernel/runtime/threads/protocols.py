"""Thread repository protocols."""

from __future__ import annotations

from typing import Any, Protocol

from app.kernel.runtime.db.models.threads import Thread, ThreadMessage


class ThreadRepositoryProtocol(Protocol):
    """Thread persistence contract used by runtime core services."""

    async def create_thread(self, thread: Thread) -> Thread: ...

    async def get_thread(self, thread_id: str) -> Thread | None: ...

    async def update_thread(self, thread_id: str, **kwargs: Any) -> Thread | None: ...

    async def soft_delete_thread(self, thread_id: str) -> Thread | None: ...

    async def add_message(self, message: ThreadMessage) -> ThreadMessage: ...


__all__ = ["ThreadRepositoryProtocol"]
