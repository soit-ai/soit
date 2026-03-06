""" handlers

Bot handlers (thin orchestration).
"""

from datetime import datetime
from typing import Optional, Dict, Any, Literal

from app.kernel.contracts.context import RequestContext
from app.modules.bot.application.app_facade import BotAppFacadeService
from app.modules.bot.application.schemas import (
    BotCreate,
    BotUpdate,
    BotVersionCreate,
    BotVersionUpdate,
    BotPublishRequest,
    BotExecuteRequest,
    BotTriggerExecuteRequest,
    BotResponse,
    BotVersionResponse,
    BotExecuteResponse,
    BotMetricsResponse,
    BotRunLogEntry,
)
from app.infra.db.pagination import PaginatedResponse, parse_page_params


class BotHandlers:
    """Handlers for bot API endpoints."""

    def __init__(self, service: BotAppFacadeService):
        self.service = service

    def _as_bot_response(self, app) -> BotResponse:
        return BotResponse(
            id=app.id,
            tenant_id=app.tenant_id,
            workspace_id=app.workspace_id,
            name=app.name,
            description=app.description,
            status=app.status,
            visibility=app.visibility,
            tags=app.tags,
            current_version_id=app.current_version_id,
            published_version_id=app.published_version_id,
            created_by=app.created_by,
            updated_by=getattr(app, "updated_by", None),
            created_at=app.created_at,
            updated_at=app.updated_at,
            deleted_at=getattr(app, "deleted_at", None),
        )

    def _as_version_response(self, version) -> BotVersionResponse:
        spec = version.spec_json or {}
        chat_spec = spec.get("chat") or {}
        metadata = spec.get("metadata") or {}
        model = chat_spec.get("model") or {}
        model_ref = chat_spec.get("model_ref")
        if not model_ref:
            if isinstance(model, str):
                model_ref = model
            elif isinstance(model, dict):
                model_ref = model.get("ref_key")
                if not model_ref:
                    provider = model.get("provider")
                    model_name = model.get("model")
                    if provider and model_name:
                        model_ref = f"model:{provider}:{model_name}"
        return BotVersionResponse(
            id=version.id,
            bot_id=version.app_id,
            version=str(version.version),
            status=version.status,
            system_prompt=chat_spec.get("system_prompt"),
            model_ref=model_ref,
            temperature=chat_spec.get("temperature"),
            max_tokens=chat_spec.get("max_tokens"),
            top_p=chat_spec.get("top_p"),
            tool_refs=chat_spec.get("tool_refs") or (chat_spec.get("tools") or {}).get("allowlist"),
            metadata_json=metadata,
            display_version=metadata.get("display_version"),
            triggers=spec.get("triggers"),
            channels=spec.get("channels"),
            limits=spec.get("limits"),
            created_by=version.created_by,
            created_at=version.created_at,
        )

    async def create_bot(self, ctx: RequestContext, data: BotCreate) -> BotResponse:
        bot = await self.service.create_bot(data)
        return self._as_bot_response(bot)

    async def update_bot(self, ctx: RequestContext, bot_id: str, data: BotUpdate) -> BotResponse:
        bot = await self.service.update_bot(bot_id, data)
        return self._as_bot_response(bot)

    async def get_bot(self, ctx: RequestContext, bot_id: str) -> BotResponse:
        bot = await self.service.get_bot(bot_id)
        return self._as_bot_response(bot)

    async def list_bots(
        self,
        ctx: RequestContext,
        page_token: Optional[str],
        page_size: int,
    ) -> PaginatedResponse[BotResponse]:
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        bots = await self.service.list_bots(limit=limit, offset=offset)
        items = [self._as_bot_response(bot) for bot in bots]
        has_next = len(bots) == limit
        next_offset = offset + len(bots) if has_next else None
        return PaginatedResponse.create(items=items, page_size=len(items), has_next=has_next, next_offset=next_offset)

    async def delete_bot(self, ctx: RequestContext, bot_id: str) -> None:
        await self.service.delete_bot(bot_id)

    async def create_version(
        self,
        ctx: RequestContext,
        bot_id: str,
        data: BotVersionCreate,
    ) -> BotVersionResponse:
        version = await self.service.create_version(bot_id, data)
        return self._as_version_response(version)

    async def update_version(
        self,
        ctx: RequestContext,
        bot_id: str,
        version_id: str,
        data: BotVersionUpdate,
    ) -> BotVersionResponse:
        version = await self.service.update_version(bot_id, version_id, data)
        return self._as_version_response(version)

    async def get_version(self, ctx: RequestContext, bot_id: str, version_id: str) -> BotVersionResponse:
        version = await self.service.get_version(bot_id, version_id)
        return self._as_version_response(version)

    async def list_versions(
        self,
        ctx: RequestContext,
        bot_id: str,
        page_token: Optional[str],
        page_size: int,
    ) -> PaginatedResponse[BotVersionResponse]:
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        versions = await self.service.list_versions(bot_id, limit=limit, offset=offset)
        items = [self._as_version_response(v) for v in versions]
        has_next = len(versions) == limit
        next_offset = offset + len(versions) if has_next else None
        return PaginatedResponse.create(items=items, page_size=len(items), has_next=has_next, next_offset=next_offset)

    async def publish_version(
        self,
        ctx: RequestContext,
        bot_id: str,
        data: BotPublishRequest,
    ) -> BotResponse:
        bot = await self.service.publish_version(bot_id, data.version_id)
        return self._as_bot_response(bot)

    async def execute_bot(
        self,
        ctx: RequestContext,
        bot_id: str,
        data: BotExecuteRequest,
    ) -> BotExecuteResponse:
        result = await self.service.execute_bot(bot_id, data)
        return BotExecuteResponse(**result)

    async def execute_bot_trigger(
        self,
        ctx: RequestContext,
        bot_id: str,
        trigger: Literal["webhook", "schedule", "event"],
        data: BotTriggerExecuteRequest,
    ) -> BotExecuteResponse:
        request = BotExecuteRequest(
            version_id=data.version_id,
            messages=data.messages,
            trigger=trigger,
            event_payload=data.event_payload,
        )
        result = await self.service.execute_bot(bot_id, request)
        return BotExecuteResponse(**result)

    async def list_runs(
        self,
        ctx: RequestContext,
        bot_id: str,
        page_token: Optional[str],
        page_size: int,
        status: Optional[str],
        started_after: Optional[datetime],
        started_before: Optional[datetime],
    ) -> PaginatedResponse[Dict[str, Any]]:
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        runs = await self.service.list_runs(
            bot_id,
            limit=limit,
            offset=offset,
            status=status,
            started_after=started_after,
            started_before=started_before,
        )
        has_next = len(runs) == limit
        next_offset = offset + len(runs) if has_next else None
        return PaginatedResponse.create(items=runs, page_size=len(runs), has_next=has_next, next_offset=next_offset)

    async def get_run(self, ctx: RequestContext, bot_id: str, run_id: str) -> Dict[str, Any]:
        return await self.service.get_run(bot_id, run_id)

    async def list_logs(
        self,
        ctx: RequestContext,
        bot_id: str,
        page_token: Optional[str],
        page_size: int,
        status: Optional[str],
        level: Optional[str],
        started_after: Optional[datetime],
        started_before: Optional[datetime],
    ) -> PaginatedResponse[BotRunLogEntry]:
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        logs = await self.service.list_logs(
            bot_id,
            limit=limit,
            offset=offset,
            status=status,
            level=level,
            started_after=started_after,
            started_before=started_before,
        )
        items = [BotRunLogEntry.model_validate(item) for item in logs]
        has_next = len(items) == limit
        next_offset = offset + len(items) if has_next else None
        return PaginatedResponse.create(items=items, page_size=len(items), has_next=has_next, next_offset=next_offset)

    async def get_metrics(
        self,
        ctx: RequestContext,
        bot_id: str,
        range_key: str,
    ) -> BotMetricsResponse:
        return BotMetricsResponse.model_validate(await self.service.get_metrics(bot_id, range_key=range_key))
