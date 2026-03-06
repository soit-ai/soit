""" handlers

Agent handlers (thin orchestration).
"""

from typing import Optional

from app.kernel.contracts.context import RequestContext
from app.modules.agent.application.service import AgentService
from app.modules.agent.application.app_facade import AgentAppFacadeService
from app.modules.agent.application.schemas import (
    AgentRunRequest,
    AgentRunResponse,
    AgentCreate,
    AgentUpdate,
    AgentResponse,
    AgentVersionCreate,
    AgentVersionResponse,
    AgentPublishRequest,
)
from app.infra.db.pagination import PaginatedResponse, parse_page_params


class AgentHandlers:
    """Handlers for agent API endpoints."""

    def __init__(self, service: AgentService):
        self.service = service

    async def run(self, ctx: RequestContext, data: AgentRunRequest) -> AgentRunResponse:
        result = await self.service.run(data)
        return AgentRunResponse(**result)


class AgentAppHandlers:
    """Handlers for agent app CRUD endpoints."""

    def __init__(self, service: AgentAppFacadeService):
        self.service = service

    def _as_agent_response(self, app) -> AgentResponse:
        return AgentResponse(
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

    def _as_version_response(self, version) -> AgentVersionResponse:
        return AgentVersionResponse(
            id=version.id,
            agent_id=version.app_id,
            version=version.version,
            status=version.status,
            spec_schema=version.spec_schema,
            spec_json=version.spec_json or {},
            checksum=version.checksum,
            created_by=version.created_by,
            created_at=version.created_at,
        )

    async def create_agent(self, ctx: RequestContext, data: AgentCreate) -> AgentResponse:
        agent = await self.service.create_agent(data)
        return self._as_agent_response(agent)

    async def update_agent(self, ctx: RequestContext, agent_id: str, data: AgentUpdate) -> AgentResponse:
        agent = await self.service.update_agent(agent_id, data)
        return self._as_agent_response(agent)

    async def get_agent(self, ctx: RequestContext, agent_id: str) -> AgentResponse:
        agent = await self.service.get_agent(agent_id)
        return self._as_agent_response(agent)

    async def list_agents(
        self,
        ctx: RequestContext,
        page_token: Optional[str],
        page_size: int,
    ) -> PaginatedResponse[AgentResponse]:
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        agents = await self.service.list_agents(limit=limit, offset=offset)
        items = [self._as_agent_response(agent) for agent in agents]
        has_next = len(agents) == limit
        next_offset = offset + len(agents) if has_next else None
        return PaginatedResponse.create(items=items, page_size=len(items), has_next=has_next, next_offset=next_offset)

    async def delete_agent(self, ctx: RequestContext, agent_id: str) -> None:
        await self.service.delete_agent(agent_id)

    async def create_version(
        self,
        ctx: RequestContext,
        agent_id: str,
        data: AgentVersionCreate,
    ) -> AgentVersionResponse:
        version = await self.service.create_version(agent_id, data)
        return self._as_version_response(version)

    async def list_versions(
        self,
        ctx: RequestContext,
        agent_id: str,
        page_token: Optional[str],
        page_size: int,
    ) -> PaginatedResponse[AgentVersionResponse]:
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        versions = await self.service.list_versions(agent_id, limit=limit, offset=offset)
        items = [self._as_version_response(version) for version in versions]
        has_next = len(versions) == limit
        next_offset = offset + len(versions) if has_next else None
        return PaginatedResponse.create(items=items, page_size=len(items), has_next=has_next, next_offset=next_offset)

    async def publish_version(
        self,
        ctx: RequestContext,
        agent_id: str,
        data: AgentPublishRequest,
    ) -> AgentResponse:
        agent = await self.service.publish_version(agent_id, data.version_id)
        return self._as_agent_response(agent)

    async def execute_agent(self, ctx: RequestContext, agent_id: str, data: AgentRunRequest) -> AgentRunResponse:
        payload = data.model_dump(exclude_none=True)
        result = await self.service.execute_agent(agent_id, payload)
        return AgentRunResponse(
            run_id=result.get("run_id"),
            output=result.get("output") or "",
            model=result.get("model") or "",
            iterations=result.get("iterations") or 0,
            tokens_prompt=result.get("tokens_prompt") or 0,
            tokens_completion=result.get("tokens_completion") or 0,
            finish_reason=result.get("finish_reason"),
            tool_calls=result.get("tool_calls") or 0,
            llm_calls=result.get("llm_calls") or 0,
            failures=result.get("failures") or 0,
            budget_exceeded=result.get("budget_exceeded") or False,
            budget_reason=result.get("budget_reason"),
            cost_total=result.get("cost_total") or 0.0,
        )
