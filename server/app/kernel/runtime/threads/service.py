"""Thread lifecycle service."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.kernel.commons.errors import NotFoundError
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.threads import Thread, ThreadMessage
from app.kernel.runtime.threads.protocols import ThreadRepositoryProtocol
from app.kernel.runtime.threads.repository import ThreadRepository


class ThreadService:
    """Coordinates thread and message persistence."""

    def __init__(
        self,
        db: Session,
        ctx: RequestContext,
        *,
        thread_repo: ThreadRepositoryProtocol | None = None,
    ) -> None:
        self.db = db
        self.ctx = ctx
        self.thread_repo = thread_repo or ThreadRepository(db, ctx)

    def create_thread(
        self,
        *,
        agent_id: str | None,
        title: str | None = None,
        metadata: dict[str, Any] | None = None,
        summary: str | None = None,
        system_prompt: str | None = None,
        default_model_ref: str | None = None,
        default_temperature: float | None = None,
        default_max_tokens: int | None = None,
        default_top_p: float | None = None,
        context_window: int | None = None,
        max_history_messages: int | None = None,
        max_history_chars: int | None = None,
        knowledge_config_json: dict[str, Any] | None = None,
        tool_config_json: dict[str, Any] | None = None,
        thread_type: str = "chat",
        source: str | None = None,
        owner_user_id: str | None = None,
    ) -> Thread:
        """Create an Agent-scoped thread."""

        return self.thread_repo.create_thread(
            Thread(
                agent_id=agent_id,
                title=title,
                summary=summary,
                system_prompt=system_prompt,
                default_model_ref=default_model_ref,
                default_temperature=default_temperature,
                default_max_tokens=default_max_tokens,
                default_top_p=default_top_p,
                context_window=context_window,
                max_history_messages=max_history_messages,
                max_history_chars=max_history_chars,
                knowledge_config_json=knowledge_config_json or {},
                tool_config_json=tool_config_json or {},
                thread_type=thread_type,
                source=source or ((metadata or {}).get("source") if isinstance(metadata, dict) else None),
                owner_user_id=owner_user_id or self.ctx.user_id,
                metadata_json=metadata or {},
            )
        )
    def get_thread(self, thread_id: str) -> Thread:
        """Load a thread or fail."""

        thread = self.thread_repo.get_thread(thread_id)
        if not thread:
            raise NotFoundError(f"Thread not found: {thread_id}")
        return thread

    def update_thread(
        self,
        *,
        thread_id: str,
        title: str | None = None,
        status: str | None = None,
        metadata: dict[str, Any] | None = None,
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
        knowledge_config_json: dict[str, Any] | None = None,
        tool_config_json: dict[str, Any] | None = None,
        thread_type: str | None = None,
        source: str | None = None,
        pinned_at: Any = ...,
    ) -> Thread:
        """Update mutable thread fields."""

        thread = self.thread_repo.update_thread(
            thread_id,
            title=title,
            status=status,
            metadata=metadata,
            latest_run_id=latest_run_id,
            summary=summary,
            system_prompt=system_prompt,
            default_model_ref=default_model_ref,
            default_temperature=default_temperature,
            default_max_tokens=default_max_tokens,
            default_top_p=default_top_p,
            context_window=context_window,
            max_history_messages=max_history_messages,
            max_history_chars=max_history_chars,
            knowledge_config_json=knowledge_config_json,
            tool_config_json=tool_config_json,
            thread_type=thread_type,
            source=source,
            pinned_at=pinned_at,
        )
        if not thread:
            raise NotFoundError(f"Thread not found: {thread_id}")
        return thread

    def delete_thread(self, *, thread_id: str) -> None:
        """Soft-delete a thread."""

        thread = self.thread_repo.soft_delete_thread(thread_id)
        if not thread:
            raise NotFoundError(f"Thread not found: {thread_id}")

    def append_message(
        self,
        *,
        thread_id: str,
        role: str,
        content: str,
        run_id: str | None = None,
        task_id: str | None = None,
        response_id: str | None = None,
        parent_message_id: str | None = None,
        message_type: str = "text",
        metadata: dict[str, Any] | None = None,
        status: str = "completed",
        model_ref: str | None = None,
        tokens_prompt: int | None = None,
        tokens_completion: int | None = None,
        finish_reason: str | None = None,
        content_json: dict[str, Any] | None = None,
        summary: str | None = None,
        citations_json: list[dict[str, Any]] | None = None,
        attachments_json: list[dict[str, Any]] | None = None,
        tool_calls_json: list[dict[str, Any]] | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> ThreadMessage:
        """Append a message to a thread."""

        self.get_thread(thread_id)
        metadata_json = metadata or {}
        return self.thread_repo.add_message(
            ThreadMessage(
                thread_id=thread_id,
                run_id=run_id,
                task_id=task_id or metadata_json.get("task_id"),
                response_id=response_id or metadata_json.get("response_id"),
                parent_message_id=parent_message_id,
                role=role,
                content=content,
                message_type=message_type,
                status=status,
                model_ref=model_ref or metadata_json.get("model_ref") or metadata_json.get("model"),
                tokens_prompt=tokens_prompt if tokens_prompt is not None else metadata_json.get("tokens_prompt"),
                tokens_completion=(
                    tokens_completion if tokens_completion is not None else metadata_json.get("tokens_completion")
                ),
                finish_reason=finish_reason or metadata_json.get("finish_reason"),
                content_json=content_json or metadata_json.get("content_json") or {},
                summary=summary or metadata_json.get("summary"),
                citations_json=citations_json or metadata_json.get("citations") or [],
                attachments_json=attachments_json or metadata_json.get("attachments") or [],
                tool_calls_json=tool_calls_json or metadata_json.get("tool_calls") or [],
                error_code=error_code or metadata_json.get("error_code"),
                error_message=error_message or metadata_json.get("error_message"),
                metadata_json=metadata_json,
            )
        )
