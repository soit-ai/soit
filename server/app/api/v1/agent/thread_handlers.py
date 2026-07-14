"""Handlers for agent thread APIs."""

from __future__ import annotations

from typing import Optional

from app.infra.db.pagination import PaginatedResponse, parse_page_params
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.threads.service import ThreadService
from app.kernel.runtime.threads.schemas import ThreadCreateRequest, ThreadDetailResponse, ThreadMessageResponse, ThreadResponse, ThreadUpdateRequest
from app.modules.agent.application.thread_query_service import AgentThreadQueryService


class ThreadHandlers:
    """Thin orchestration for thread endpoints."""

    def __init__(
        self,
        query_service: AgentThreadQueryService,
        runtime_service: Optional[ThreadService] = None,
    ) -> None:
        self.query_service = query_service
        self.runtime_service = runtime_service

    def _serialize_thread(self, thread) -> ThreadResponse:
        metadata = thread.metadata_json or {}
        return ThreadResponse(
            id=thread.id,
            tenant_id=thread.tenant_id,
            workspace_id=thread.workspace_id,
            agent_id=thread.agent_id,
            title=thread.title,
            status=thread.status,
            thread_type=thread.thread_type,
            source=thread.source,
            owner_user_id=thread.owner_user_id,
            summary=thread.summary,
            system_prompt=thread.system_prompt,
            default_model_ref=thread.default_model_ref,
            default_temperature=thread.default_temperature,
            default_max_tokens=thread.default_max_tokens,
            default_top_p=thread.default_top_p,
            context_window=thread.context_window,
            max_history_messages=thread.max_history_messages,
            max_history_chars=thread.max_history_chars,
            message_count=thread.message_count,
            last_message_at=thread.last_message_at,
            last_user_message_at=thread.last_user_message_at,
            last_assistant_message_at=thread.last_assistant_message_at,
            archived_at=thread.archived_at,
            pinned_at=thread.pinned_at,
            knowledge_config_json=thread.knowledge_config_json or {},
            tool_config_json=thread.tool_config_json or {},
            metadata_json=metadata if isinstance(metadata, dict) else {},
            latest_run_id=thread.latest_run_id,
            created_by=thread.created_by,
            updated_by=thread.updated_by,
            created_at=thread.created_at,
            updated_at=thread.updated_at,
            deleted_at=thread.deleted_at,
        )

    async def list_threads(
        self,
        ctx: RequestContext,
        *,
        status: Optional[str],
        agent_id: Optional[str],
        search: Optional[str],
        page_token: Optional[str],
        page_size: int,
    ) -> PaginatedResponse[ThreadResponse]:
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        threads = self.query_service.list_threads(
            limit=limit,
            offset=offset,
            status=status,
            agent_id=agent_id,
            search=search,
        )
        items = [self._serialize_thread(thread) for thread in threads]
        has_next = len(threads) == limit
        next_offset = offset + len(threads) if has_next else None
        return PaginatedResponse.create(items=items, page_size=len(items), has_next=has_next, next_offset=next_offset)

    async def create_thread(self, ctx: RequestContext, payload: ThreadCreateRequest) -> ThreadResponse:
        del ctx
        if not self.runtime_service:
            raise RuntimeError("Thread runtime service is not configured")
        thread = self.runtime_service.create_thread(
            agent_id=payload.agent_id,
            title=payload.title,
            metadata=payload.metadata_json,
            summary=payload.summary,
            system_prompt=payload.system_prompt,
            default_model_ref=payload.default_model_ref,
            default_temperature=payload.default_temperature,
            default_max_tokens=payload.default_max_tokens,
            default_top_p=payload.default_top_p,
            context_window=payload.context_window,
            max_history_messages=payload.max_history_messages,
            max_history_chars=payload.max_history_chars,
            knowledge_config_json=payload.knowledge_config_json,
            tool_config_json=payload.tool_config_json,
            thread_type=payload.thread_type,
            source=payload.source,
            owner_user_id=payload.owner_user_id,
        )
        return self._serialize_thread(thread)

    async def get_thread(self, ctx: RequestContext, thread_id: str) -> ThreadDetailResponse:
        thread = self.query_service.get_thread(thread_id)
        messages = self.query_service.list_thread_messages(thread_id)
        return ThreadDetailResponse(
            thread=self._serialize_thread(thread),
            messages=[ThreadMessageResponse.model_validate(item) for item in messages],
        )

    async def update_thread(
        self,
        ctx: RequestContext,
        thread_id: str,
        payload: ThreadUpdateRequest,
    ) -> ThreadResponse:
        if not self.runtime_service:
            raise RuntimeError("Thread runtime service is not configured")
        pinned_at = payload.pinned_at if "pinned_at" in payload.model_fields_set else ...
        thread = self.runtime_service.update_thread(
            thread_id=thread_id,
            title=payload.title,
            status=payload.status,
            metadata=payload.metadata_json,
            summary=payload.summary,
            system_prompt=payload.system_prompt,
            default_model_ref=payload.default_model_ref,
            default_temperature=payload.default_temperature,
            default_max_tokens=payload.default_max_tokens,
            default_top_p=payload.default_top_p,
            context_window=payload.context_window,
            max_history_messages=payload.max_history_messages,
            max_history_chars=payload.max_history_chars,
            knowledge_config_json=payload.knowledge_config_json,
            tool_config_json=payload.tool_config_json,
            thread_type=payload.thread_type,
            source=payload.source,
            pinned_at=pinned_at,
        )
        return self._serialize_thread(thread)

    async def delete_thread(self, ctx: RequestContext, thread_id: str) -> None:
        del ctx
        if not self.runtime_service:
            raise RuntimeError("Thread runtime service is not configured")
        self.runtime_service.delete_thread(thread_id=thread_id)
