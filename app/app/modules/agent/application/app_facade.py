"""app_facade

Agent facade backed by unified apps/app_versions.
"""

from __future__ import annotations

from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import select, and_, desc, func

from app.kernel.contracts.context import RequestContext
from app.kernel.commons.errors import NotFoundError, ValidationError
from app.kernel.commons.time import utc_now
from app.kernel.identity.guard import rbac_guard, workspace_guard
from app.kernel.identity.permissions import RESOURCE_AGENT
from app.kernel.specs.validator import validate_runtime_spec
from app.modules.appcenter.domain.models import App, AppVersion
from app.modules.agent.application.schemas import AgentCreate, AgentUpdate, AgentVersionCreate
from app.modules.appcenter.runtime.router import AppRuntimeRouter
from app.modules.appcenter.application.publish_service import AppPublishService


class AgentAppFacadeService:
    """Agent service backed by apps/app_versions."""

    def __init__(
        self,
        db: Session,
        ctx: RequestContext,
        event_bus: Optional[Any] = None,
        publish_service: Optional[AppPublishService] = None,
    ) -> None:
        self.db = db
        self.ctx = ctx
        self.runtime_router = AppRuntimeRouter(db, ctx, event_bus=event_bus)
        self.publish_service = publish_service or AppPublishService(db, ctx)

    def _resolve_agent_create_id(self, data: AgentCreate, **kwargs) -> str:
        return data.name or f"new:{self.ctx.workspace_id}"

    def _get_agent_app(self, agent_id: str) -> App:
        app = self.db.get(App, agent_id)
        if not app or app.tenant_id != self.ctx.tenant_id or app.workspace_id != self.ctx.workspace_id:
            raise NotFoundError(f"Agent not found: {agent_id}")
        if app.type != "AGENT":
            raise NotFoundError(f"Agent not found: {agent_id}")
        return app

    def _next_version_number(self, app_id: str) -> int:
        query = select(func.max(AppVersion.version)).where(
            and_(
                AppVersion.app_id == app_id,
                AppVersion.tenant_id == self.ctx.tenant_id,
                AppVersion.workspace_id == self.ctx.workspace_id,
            )
        )
        max_val = self.db.exec(query).one()
        if hasattr(max_val, "_mapping"):
            max_val = max_val[0]
        elif isinstance(max_val, (list, tuple)):
            max_val = max_val[0] if max_val else None
        return int(max_val or 0) + 1

    def _build_spec(self, data: AgentVersionCreate) -> Dict[str, Any]:
        memory_enabled = data.memory_strategy is not None or data.memory_top_k is not None
        memory_policy: Dict[str, Any] = {}
        if data.memory_top_k is not None:
            memory_policy["top_k"] = data.memory_top_k
        limits: Dict[str, Any] = {
            "max_iterations": data.max_iterations,
            "max_tool_calls": data.max_tool_calls,
            "max_llm_calls": data.max_llm_calls,
            "max_failures": data.max_failures,
            "timeout_ms": data.max_runtime_seconds * 1000 if data.max_runtime_seconds else None,
            "max_tokens": data.max_tokens_total,
            "budget": data.max_cost,
        }
        policies = {
            "verify": data.verify,
            "failure_strategy": data.failure_strategy,
            "cost_currency": data.cost_currency,
        }
        return {
            "runtime": "agent_runtime_v1",
            "planner": None,
            "system_prompt": data.system_prompt,
            "model": {"ref_key": data.model_ref},
            "tools": {
                "allowlist": data.tool_refs,
                "configs": None,
            },
            "memory": {
                "enabled": memory_enabled or None,
                "type": data.memory_strategy,
                "policy": memory_policy or None,
            },
            "rag": None,
            "limits": limits,
            "policies": policies,
        }

    @rbac_guard(RESOURCE_AGENT, "create", resource_id_resolver=_resolve_agent_create_id)
    async def create_agent(self, data: AgentCreate) -> App:
        query = select(App).where(
            and_(
                App.tenant_id == self.ctx.tenant_id,
                App.workspace_id == self.ctx.workspace_id,
                App.type == "AGENT",
                App.name == data.name,
            )
        )
        existing = self.db.exec(query).first()
        if existing:
            raise ValidationError(f"Agent with name '{data.name}' already exists")

        app = App(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            type="AGENT",
            status="active",
            visibility=data.visibility,
            name=data.name,
            description=data.description,
            tags=data.tags,
            created_by=self.ctx.user_id,
        )
        self.db.add(app)
        self.db.commit()
        self.db.refresh(app)
        return app

    @rbac_guard(RESOURCE_AGENT, "update", resource_id_arg="agent_id")
    async def update_agent(self, agent_id: str, data: AgentUpdate) -> App:
        app = self._get_agent_app(agent_id)
        if data.name and data.name != app.name:
            query = select(App).where(
                and_(
                    App.tenant_id == self.ctx.tenant_id,
                    App.workspace_id == self.ctx.workspace_id,
                    App.type == "AGENT",
                    App.name == data.name,
                    App.id != agent_id,
                )
            )
            existing = self.db.exec(query).first()
            if existing:
                raise ValidationError(f"Agent with name '{data.name}' already exists")
            app.name = data.name

        if data.description is not None:
            app.description = data.description
        if data.status is not None:
            app.status = data.status
        if data.visibility is not None:
            app.visibility = data.visibility
        if data.tags is not None:
            app.tags = data.tags
        app.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(app)
        return app

    @rbac_guard(RESOURCE_AGENT, "read", resource_id_arg="agent_id")
    async def get_agent(self, agent_id: str) -> App:
        return self._get_agent_app(agent_id)

    @workspace_guard("read")
    async def list_agents(self, limit: int = 20, offset: int = 0) -> List[App]:
        query = select(App).where(
            and_(
                App.tenant_id == self.ctx.tenant_id,
                App.workspace_id == self.ctx.workspace_id,
                App.type == "AGENT",
                App.status != "archived",
            )
        ).order_by(desc(App.created_at)).offset(offset).limit(limit)
        results = list(self.db.exec(query).all())
        if not results:
            return []
        if isinstance(results[0], App):
            return results
        return [row[0] for row in results if row]

    @rbac_guard(RESOURCE_AGENT, "delete", resource_id_arg="agent_id")
    async def delete_agent(self, agent_id: str) -> None:
        app = self._get_agent_app(agent_id)
        app.status = "archived"
        app.updated_at = utc_now()
        self.db.commit()

    @rbac_guard(RESOURCE_AGENT, "update", resource_id_arg="agent_id")
    async def create_version(self, agent_id: str, data: AgentVersionCreate) -> AppVersion:
        app = self._get_agent_app(agent_id)
        spec = self._build_spec(data)
        validate_runtime_spec("agent.v1", spec, raise_on_error=True)

        version = AppVersion(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            app_id=agent_id,
            version=self._next_version_number(agent_id),
            status="draft",
            spec_schema="agent.v1",
            spec_json=spec,
            created_by=self.ctx.user_id,
        )
        self.db.add(version)
        self.db.commit()
        self.db.refresh(version)

        app.current_version_id = version.id
        app.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(app)
        return version

    @rbac_guard(RESOURCE_AGENT, "read", resource_id_arg="agent_id")
    async def list_versions(self, agent_id: str, limit: int = 20, offset: int = 0) -> List[AppVersion]:
        self._get_agent_app(agent_id)
        query = select(AppVersion).where(
            and_(
                AppVersion.app_id == agent_id,
                AppVersion.tenant_id == self.ctx.tenant_id,
                AppVersion.workspace_id == self.ctx.workspace_id,
            )
        ).order_by(desc(AppVersion.created_at)).offset(offset).limit(limit)
        results = list(self.db.exec(query).all())
        return [item if isinstance(item, AppVersion) else item[0] for item in results]

    @rbac_guard(RESOURCE_AGENT, "update", resource_id_arg="agent_id")
    async def publish_version(self, agent_id: str, version_id: str) -> App:
        app = self._get_agent_app(agent_id)
        version = self.db.get(AppVersion, version_id)
        if not version or version.app_id != agent_id:
            raise NotFoundError(f"Version not found: {version_id}")
        self.publish_service.publish(agent_id, version_id)
        self.db.refresh(app)
        return app

    @rbac_guard(RESOURCE_AGENT, "run", resource_id_arg="agent_id")
    async def execute_agent(self, agent_id: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        app = self._get_agent_app(agent_id)
        result = await self.runtime_router.execute(
            app_id=app.id,
            inputs=inputs,
            use_current=True,
        )
        output = result.get("output") or {}
        return {
            "run_id": result.get("run_id"),
            "output": output.get("output") or "",
            "model": output.get("model") or "",
            "iterations": output.get("iterations") or 0,
        }
