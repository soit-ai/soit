"""Thread repository protocols."""

from __future__ import annotations

from typing import Any, Protocol

from app.kernel.runtime.db.models.threads import Thread, ThreadMessage


class ThreadRepositoryProtocol(Protocol):
    """Thread persistence contract used by runtime core services."""

    def create_thread(self, thread: Thread) -> Thread: ...

    def get_thread(self, thread_id: str) -> Thread | None: ...

    def update_thread(self, thread_id: str, **kwargs: Any) -> Thread | None: ...

    def soft_delete_thread(self, thread_id: str) -> Thread | None: ...

    def add_message(self, message: ThreadMessage) -> ThreadMessage: ...



__all__ = ["ThreadRepositoryProtocol"]
