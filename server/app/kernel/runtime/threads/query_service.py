"""Read-side services for runtime threads."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.kernel.commons.errors import NotFoundError
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.threads import Thread
from app.kernel.runtime.threads.repository import ThreadRepository


class ThreadQueryService:
    """Read-only access to thread records."""

    def __init__(self, db: Session, ctx: RequestContext) -> None:
        self.db = db
        self.ctx = ctx
        self.thread_repo = ThreadRepository(db, ctx)

    def list_threads(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        status: str | None = None,
        agent_id: str | None = None,
    ) -> list[Thread]:
        return self.thread_repo.list_threads(
            limit=limit,
            offset=offset,
            status=status,
            agent_id=agent_id,
        )

    def get_thread(self, thread_id: str) -> Thread:
        thread = self.thread_repo.get_thread(thread_id)
        if not thread:
            raise NotFoundError(f"Thread not found: {thread_id}")
        return thread

    def list_thread_messages(self, thread_id: str):
        self.get_thread(thread_id)
        return self.thread_repo.list_messages(thread_id)
