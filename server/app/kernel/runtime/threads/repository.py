"""Thread repositories."""

from __future__ import annotations

from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import Session

from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.threads import Thread, ThreadMessage


class ThreadRepository:
    """Repository for Agent-scoped threads and messages."""

    def __init__(self, db: Session, ctx: RequestContext) -> None:
        self.db = db
        self.ctx = ctx

    def create_thread(self, thread: Thread) -> Thread:
        thread.tenant_id = self.ctx.tenant_id
        thread.workspace_id = self.ctx.workspace_id
        thread.created_by = self.ctx.user_id
        thread.updated_by = self.ctx.user_id
        thread.owner_user_id = thread.owner_user_id or self.ctx.user_id
        self.db.add(thread)
        self.db.flush()
        self.db.refresh(thread)
        return thread

    def get_thread(self, thread_id: str) -> Thread | None:
        query = select(Thread).where(
            and_(
                Thread.id == thread_id,
                Thread.tenant_id == self.ctx.tenant_id,
                Thread.workspace_id == self.ctx.workspace_id,
                Thread.deleted_at.is_(None),
            )
        )
        result = self.db.exec(query).first()
        return result if isinstance(result, Thread) else result[0] if result else None

    def list_threads(
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
        results = list(self.db.exec(query).all())
        return [item if isinstance(item, Thread) else item[0] for item in results]

    def _next_message_sequence(self, thread_id: str) -> int:
        query = select(func.max(ThreadMessage.sequence_no)).where(
            and_(
                ThreadMessage.thread_id == thread_id,
                ThreadMessage.tenant_id == self.ctx.tenant_id,
                ThreadMessage.workspace_id == self.ctx.workspace_id,
            )
        )
        result = self.db.exec(query).first()
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

    def add_message(self, message: ThreadMessage) -> ThreadMessage:
        thread = self.get_thread(message.thread_id)
        if not thread:
            raise ValueError(f"Thread not found: {message.thread_id}")

        message.tenant_id = self.ctx.tenant_id
        message.workspace_id = self.ctx.workspace_id
        message.created_by = self.ctx.user_id
        message.sequence_no = message.sequence_no or self._next_message_sequence(message.thread_id)
        message.status = message.status or "completed"
        message.content_json = message.content_json or self._default_content_json(message.content, message.message_type)
        message.summary = message.summary or self._default_summary(message.content)
        message.citations_json = message.citations_json or []
        message.attachments_json = message.attachments_json or []
        message.tool_calls_json = message.tool_calls_json or []
        if message.parent_message_id:
            parent = self.db.get(ThreadMessage, message.parent_message_id)
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
        self.db.flush()
        self.db.refresh(message)
        return message

    def list_messages(self, thread_id: str) -> list[ThreadMessage]:
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
        results = list(self.db.exec(query).all())
        return [item if isinstance(item, ThreadMessage) else item[0] for item in results]

    def touch_thread(self, thread: Thread, *, latest_run_id: str | None = None) -> Thread:
        thread.updated_at = utc_now()
        thread.updated_by = self.ctx.user_id
        if latest_run_id is not None:
            thread.latest_run_id = latest_run_id
        if thread.status == "archived" and thread.archived_at is None:
            thread.archived_at = thread.updated_at
        elif thread.status != "archived":
            thread.archived_at = None
        self.db.add(thread)
        self.db.flush()
        self.db.refresh(thread)
        return thread

    def update_thread(
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
        thread = self.get_thread(thread_id)
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
        return self.touch_thread(thread, latest_run_id=latest_run_id)

    def soft_delete_thread(self, thread_id: str) -> Thread | None:
        thread = self.get_thread(thread_id)
        if not thread:
            return None
        thread.deleted_at = utc_now()
        thread.status = "deleted"
        return self.touch_thread(thread)
