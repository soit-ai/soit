"""Thread repositories."""

from __future__ import annotations

from sqlalchemy import Integer, and_, desc, func, literal, select
from sqlalchemy.orm import aliased
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.common.sequence_cursor import allocate_sequence
from app.kernel.runtime.db.models.threads import Thread, ThreadMessage
from app.settings.settings import settings

LINEAGE_HARD_CAP = 2000
"""Deepest branch a lineage walk will follow, whatever the window asked for."""


class ThreadRepository:
    """Repository for Agent-scoped threads and messages."""

    def __init__(self, db: AsyncSession, ctx: RequestContext) -> None:
        self.db = db
        self.ctx = ctx

    async def create_thread(self, thread: Thread) -> Thread:
        thread.tenant_id = self.ctx.tenant_id
        thread.workspace_id = self.ctx.workspace_id
        thread.created_by = self.ctx.user_id
        thread.updated_by = self.ctx.user_id
        thread.owner_user_id = thread.owner_user_id or self.ctx.user_id
        self.db.add(thread)
        await self.db.flush()
        return thread

    async def get_thread(self, thread_id: str) -> Thread | None:
        # By primary key through the identity map (no round trip for a thread
        # this session already holds); scope and soft-delete checks unchanged.
        thread = await self.db.get(Thread, thread_id)
        if thread is None or thread.deleted_at is not None:
            return None
        if thread.tenant_id != self.ctx.tenant_id or thread.workspace_id != self.ctx.workspace_id:
            return None
        return thread

    async def list_threads(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        status: str | None = None,
        agent_id: str | None = None,
    ) -> list[Thread]:
        filters = [
            Thread.tenant_id == self.ctx.tenant_id,
            Thread.workspace_id == self.ctx.workspace_id,
            Thread.deleted_at.is_(None),
        ]
        if status:
            filters.append(Thread.status == status)
        if agent_id:
            filters.append(Thread.agent_id == agent_id)

        query = (
            select(Thread)
            .where(and_(*filters))
            .order_by(desc(Thread.pinned_at), desc(Thread.updated_at), desc(Thread.id))
            .offset(offset)
            .limit(limit)
        )
        results = list((await self.db.exec(query)).all())
        return [item if isinstance(item, Thread) else item[0] for item in results]

    async def _next_message_sequence(self, thread_id: str) -> int:
        query = select(func.max(ThreadMessage.sequence_no)).where(
            and_(
                ThreadMessage.thread_id == thread_id,
                ThreadMessage.tenant_id == self.ctx.tenant_id,
                ThreadMessage.workspace_id == self.ctx.workspace_id,
            )
        )
        result = (await self.db.exec(query)).first()
        max_val = result if isinstance(result, int) else result[0] if result else None
        return int(max_val or 0) + 1

    @staticmethod
    def _default_content_json(content: str, message_type: str) -> dict:
        return {
            "type": message_type or "text",
            "text": content,
            "parts": [{"type": "text", "text": content}],
        }

    @staticmethod
    def _default_summary(content: str) -> str:
        normalized = " ".join((content or "").split())
        return normalized[:280]

    async def add_message(self, message: ThreadMessage) -> ThreadMessage:
        thread_result = (
            await self.db.exec(
                select(Thread)
                .where(
                    and_(
                        Thread.id == message.thread_id,
                        Thread.tenant_id == self.ctx.tenant_id,
                        Thread.workspace_id == self.ctx.workspace_id,
                        Thread.deleted_at.is_(None),
                    )
                )
                .with_for_update()
            )
        ).first()
        thread = (
            thread_result
            if isinstance(thread_result, Thread)
            else thread_result[0]
            if thread_result
            else None
        )
        if not thread:
            raise ValueError(f"Thread not found: {message.thread_id}")

        message.tenant_id = self.ctx.tenant_id
        message.workspace_id = self.ctx.workspace_id
        message.created_by = self.ctx.user_id
        # The thread row locked above stays locked until commit, so only the
        # first message of a transaction reads MAX(sequence_no).
        message.sequence_no = message.sequence_no or await allocate_sequence(
            self.db,
            "thread_message",
            message.thread_id,
            lambda: self._next_message_sequence(message.thread_id),
        )
        message.status = message.status or "completed"
        message.content_json = message.content_json or self._default_content_json(
            message.content, message.message_type
        )
        message.summary = message.summary or self._default_summary(message.content)
        message.citations_json = message.citations_json or []
        message.attachments_json = message.attachments_json or []
        message.tool_calls_json = message.tool_calls_json or []
        if message.parent_message_id:
            parent = await self.db.get(ThreadMessage, message.parent_message_id)
            if not parent or parent.thread_id != message.thread_id:
                raise ValueError("parent_message_id must belong to the same thread")

        thread.updated_at = message.created_at or utc_now()
        thread.updated_by = self.ctx.user_id
        thread.message_count = int(thread.message_count or 0) + 1
        thread.last_message_at = message.created_at
        if message.role == "user":
            thread.last_user_message_at = message.created_at
            if not thread.title:
                thread.title = self._default_summary(message.content)[:120]
        elif message.role == "assistant":
            thread.last_assistant_message_at = message.created_at
        if message.run_id:
            thread.latest_run_id = message.run_id
        if not thread.summary and message.role in {"user", "assistant"}:
            thread.summary = message.summary

        self.db.add(thread)
        self.db.add(message)
        await self.db.flush()
        return message

    async def list_messages(self, thread_id: str) -> list[ThreadMessage]:
        query = (
            select(ThreadMessage)
            .where(
                and_(
                    ThreadMessage.thread_id == thread_id,
                    ThreadMessage.tenant_id == self.ctx.tenant_id,
                    ThreadMessage.workspace_id == self.ctx.workspace_id,
                    ThreadMessage.deleted_at.is_(None),
                )
            )
            .order_by(ThreadMessage.sequence_no.asc(), ThreadMessage.created_at.asc())
        )
        results = list((await self.db.exec(query)).all())
        return [item if isinstance(item, ThreadMessage) else item[0] for item in results]

    def _message_scope(self, thread_id: str):
        return (
            ThreadMessage.thread_id == thread_id,
            ThreadMessage.tenant_id == self.ctx.tenant_id,
            ThreadMessage.workspace_id == self.ctx.workspace_id,
            ThreadMessage.deleted_at.is_(None),
        )

    async def latest_message_id(self, thread_id: str) -> str | None:
        """Id of the ledger's last message, without loading the ledger."""
        query = (
            select(ThreadMessage.id)
            .where(and_(*self._message_scope(thread_id)))
            .order_by(ThreadMessage.sequence_no.desc(), ThreadMessage.created_at.desc())
            .limit(1)
        )
        return (await self.db.exec(query)).scalars().first()

    async def find_by_agui_message_id(self, thread_id: str, agui_message_id: str) -> ThreadMessage | None:
        """The message a client-supplied AG-UI message id was stored under."""
        query = (
            select(ThreadMessage)
            .where(
                and_(
                    *self._message_scope(thread_id),
                    ThreadMessage.metadata_json["agui_message_id"].as_string() == agui_message_id,
                )
            )
            .order_by(ThreadMessage.sequence_no.asc())
            .limit(1)
        )
        return (await self.db.exec(query)).scalars().first()

    async def get_message(self, thread_id: str, message_id: str) -> ThreadMessage | None:
        """Return one scoped message that belongs to the requested thread."""

        query = select(ThreadMessage).where(
            and_(
                ThreadMessage.id == message_id,
                ThreadMessage.thread_id == thread_id,
                ThreadMessage.tenant_id == self.ctx.tenant_id,
                ThreadMessage.workspace_id == self.ctx.workspace_id,
                ThreadMessage.deleted_at.is_(None),
            )
        )
        result = (await self.db.exec(query)).first()
        return result if isinstance(result, ThreadMessage) else result[0] if result else None

    async def message_lineage(
        self, thread_id: str, head_message_id: str, *, limit: int | None = None
    ) -> list[ThreadMessage]:
        """Resolve the conversation branch ending at ``head_message_id``, root-most first.

        The walk follows ``parent_message_id`` from the head in one recursive
        query and stops after ``limit`` messages (the configured history
        window when not given), so a turn on a long conversation reads its
        window, not the ledger. Branches are read from the head, which is
        why the window keeps the newest messages.
        """

        window = limit if limit is not None else settings.thread_history_max_messages
        window = max(1, min(int(window), LINEAGE_HARD_CAP))
        scope = self._message_scope(thread_id)
        head = (
            select(
                ThreadMessage.id.label("id"),
                ThreadMessage.parent_message_id.label("parent_message_id"),
                literal(0, Integer).label("depth"),
            )
            .where(and_(ThreadMessage.id == head_message_id, *scope))
            .cte("lineage", recursive=True)
        )
        parent = aliased(ThreadMessage)
        # The recursive term joins on the primary key only. Adding the thread
        # scope here lets the planner pick the thread index for a freshly
        # written thread it has no statistics for, and then walk all of that
        # thread's rows on every step; the scope is checked on the rows below.
        walk = (
            select(
                parent.id.label("id"),
                parent.parent_message_id.label("parent_message_id"),
                (head.c.depth + 1).label("depth"),
            )
            .join(head, parent.id == head.c.parent_message_id)
            .where(and_(parent.deleted_at.is_(None), head.c.depth + 1 < window))
        )
        lineage = head.union_all(walk)
        query = (
            select(ThreadMessage, lineage.c.depth)
            .join(lineage, ThreadMessage.id == lineage.c.id)
            .order_by(lineage.c.depth.desc())
        )
        rows = (await self.db.exec(query)).all()
        if not rows:
            raise ValueError("Thread message lineage references an unknown message")
        messages = [row[0] for row in rows]
        if len({message.id for message in messages}) != len(messages):
            raise ValueError("Thread message lineage contains a cycle")
        if any(
            message.thread_id != thread_id
            or message.tenant_id != self.ctx.tenant_id
            or message.workspace_id != self.ctx.workspace_id
            for message in messages
        ):
            raise ValueError("Thread message lineage references an unknown message")
        root_most = messages[0]
        if root_most.parent_message_id is not None and len(messages) < window:
            # The walk stopped before the window was full: the parent it
            # points at is not in this thread's live ledger.
            raise ValueError("Thread message lineage references an unknown message")
        return messages

    async def touch_thread(self, thread: Thread, *, latest_run_id: str | None = None) -> Thread:
        thread.updated_at = utc_now()
        thread.updated_by = self.ctx.user_id
        if latest_run_id is not None:
            thread.latest_run_id = latest_run_id
        if thread.status == "archived" and thread.archived_at is None:
            thread.archived_at = thread.updated_at
        elif thread.status != "archived":
            thread.archived_at = None
        self.db.add(thread)
        await self.db.flush()
        return thread

    async def update_thread(
        self,
        thread_id: str,
        *,
        title: str | None = None,
        status: str | None = None,
        metadata: dict | None = None,
        latest_run_id: str | None = None,
        summary: str | None = None,
        system_prompt: str | None = None,
        default_model_ref: str | None = None,
        default_temperature: float | None = None,
        default_max_tokens: int | None = None,
        default_top_p: float | None = None,
        context_window: int | None = None,
        max_history_messages: int | None = None,
        max_history_chars: int | None = None,
        knowledge_config_json: dict | None = None,
        tool_config_json: dict | None = None,
        thread_type: str | None = None,
        source: str | None = None,
        pinned_at: object = ...,
    ) -> Thread | None:
        thread = await self.get_thread(thread_id)
        if not thread:
            return None
        if title is not None:
            thread.title = title
        if status is not None:
            thread.status = status
        if metadata is not None:
            thread.metadata_json = metadata
        if summary is not None:
            thread.summary = summary
        if system_prompt is not None:
            thread.system_prompt = system_prompt
        if default_model_ref is not None:
            thread.default_model_ref = default_model_ref
        if default_temperature is not None:
            thread.default_temperature = default_temperature
        if default_max_tokens is not None:
            thread.default_max_tokens = default_max_tokens
        if default_top_p is not None:
            thread.default_top_p = default_top_p
        if context_window is not None:
            thread.context_window = context_window
        if max_history_messages is not None:
            thread.max_history_messages = max_history_messages
        if max_history_chars is not None:
            thread.max_history_chars = max_history_chars
        if knowledge_config_json is not None:
            thread.knowledge_config_json = knowledge_config_json
        if tool_config_json is not None:
            thread.tool_config_json = tool_config_json
        if thread_type is not None:
            thread.thread_type = thread_type
        if source is not None:
            thread.source = source
        if pinned_at is not ...:
            thread.pinned_at = pinned_at
        return await self.touch_thread(thread, latest_run_id=latest_run_id)

    async def soft_delete_thread(self, thread_id: str) -> Thread | None:
        thread = await self.get_thread(thread_id)
        if not thread:
            return None
        thread.deleted_at = utc_now()
        thread.status = "deleted"
        return await self.touch_thread(thread)
