"""Agent thread read-side queries."""

from __future__ import annotations

from sqlalchemy import and_, desc, or_, select
from sqlalchemy.orm import Session

from app.kernel.commons.errors import NotFoundError
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.threads import Thread, ThreadMessage
from app.kernel.runtime.threads.repository import ThreadRepository


class AgentThreadQueryService:
    """Read-side queries for agent-backed runtime threads."""

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
        search: str | None = None,
    ) -> list[Thread]:
        normalized_search = (search or "").strip()
        if not normalized_search:
            return self.thread_repo.list_threads(
                limit=limit,
                offset=offset,
                status=status,
                agent_id=agent_id,
            )

        filters = [
            Thread.tenant_id == self.ctx.tenant_id,
            Thread.workspace_id == self.ctx.workspace_id,
            Thread.deleted_at.is_(None),
        ]
        if status:
            filters.append(Thread.status == status)
        if agent_id:
            filters.append(Thread.agent_id == agent_id)

        pattern = f"%{normalized_search}%"
        message_match = (
            select(ThreadMessage.id)
            .where(
                and_(
                    ThreadMessage.thread_id == Thread.id,
                    ThreadMessage.tenant_id == self.ctx.tenant_id,
                    ThreadMessage.workspace_id == self.ctx.workspace_id,
                    ThreadMessage.deleted_at.is_(None),
                    or_(
                        ThreadMessage.content.ilike(pattern),
                        ThreadMessage.summary.ilike(pattern),
                    ),
                )
            )
            .exists()
        )
        filters.append(
            or_(
                Thread.title.ilike(pattern),
                Thread.summary.ilike(pattern),
                message_match,
            )
        )

        query = (
            select(Thread)
            .where(and_(*filters))
            .order_by(desc(Thread.pinned_at), desc(Thread.updated_at), desc(Thread.id))
            .offset(offset)
            .limit(limit)
        )
        results = list(self.db.exec(query).all())
        return [item if isinstance(item, Thread) else item[0] for item in results]

    def get_thread(self, thread_id: str) -> Thread:
        thread = self.thread_repo.get_thread(thread_id)
        if not thread:
            raise NotFoundError(f"Thread not found: {thread_id}")
        return thread

    def list_thread_messages(self, thread_id: str) -> list[ThreadMessage]:
        self.get_thread(thread_id)
        return self.thread_repo.list_messages(thread_id)
