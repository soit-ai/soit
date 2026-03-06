"""runtime

App runtime router - routes unified app execution to the correct runtime.

Moved from app.kernel.execution to avoid kernel -> modules dependency.
"""

from __future__ import annotations

from typing import Optional, Dict, Any

from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.kernel.commons.errors import NotFoundError, ValidationError
from app.kernel.events.bus import EventBus
from app.kernel.specs.validator import validate_runtime_spec
from app.modules.appcenter.domain.models import App, AppVersion
from app.modules.chat.runtime.chat_executor import ChatExecutorV1
from app.modules.bot.runtime.bot_executor import BotExecutorV1
from app.modules.agent.runtime.agent_executor import AgentExecutorV1
from app.modules.workflow.runtime.workflow_executor import WorkflowExecutorV1


class AppRuntimeRouter:
    """Route execution to runtime based on app type and spec schema."""

    def __init__(
        self,
        db: Session,
        ctx: RequestContext,
        *,
        event_bus: Optional[EventBus] = None,
    ) -> None:
        self.db = db
        self.ctx = ctx
        self.event_bus = event_bus
        self.workflow_executor = WorkflowExecutorV1(db, ctx, event_bus=event_bus)
        self.chat_executor = ChatExecutorV1(db, ctx, event_bus=event_bus)
        self.bot_executor = BotExecutorV1(db, ctx, event_bus=event_bus)
        self.agent_executor = AgentExecutorV1(db, ctx, event_bus=event_bus)

    def _get_app(self, app_id: str) -> App:
        app = self.db.get(App, app_id)
        if not app or app.tenant_id != self.ctx.tenant_id or app.workspace_id != self.ctx.workspace_id:
            raise NotFoundError(f"App not found: {app_id}")
        return app

    def _get_version(self, app: App, version_id: Optional[str]) -> AppVersion:
        version_id = version_id or app.current_version_id
        if not version_id:
            raise NotFoundError("App has no current version")
        version = self.db.get(AppVersion, version_id)
        if not version or version.app_id != app.id:
            raise NotFoundError(f"App version not found: {version_id}")
        return version

    async def execute(
        self,
        *,
        app_id: str,
        inputs: Dict[str, Any],
        version_id: Optional[str] = None,
        use_current: bool = True,
    ) -> Dict[str, Any]:
        """Execute an app version and return run info + output."""
        app = self._get_app(app_id)
        version = self._get_version(app, version_id if not use_current else None)

        spec_schema = (version.spec_schema or "").lower()
        if app.type == "DATASET":
            raise ValidationError("Dataset apps cannot be executed via AppCenter runtime")
        if app.type == "WORKFLOW" and spec_schema == "workflow.v1":
            validate_runtime_spec("workflow.v1", version.spec_json, raise_on_error=True)
            return await self.workflow_executor.execute(app=app, version=version, inputs=inputs)

        if app.type == "CHAT" and spec_schema == "chat.v1":
            validate_runtime_spec("chat.v1", version.spec_json, raise_on_error=True)
            return await self.chat_executor.execute(app=app, version=version, inputs=inputs)

        if app.type == "BOT" and spec_schema == "bot.v1":
            validate_runtime_spec("bot.v1", version.spec_json, raise_on_error=True)
            return await self.bot_executor.execute(app=app, version=version, inputs=inputs)

        if app.type == "AGENT" and spec_schema == "agent.v1":
            validate_runtime_spec("agent.v1", version.spec_json, raise_on_error=True)
            return await self.agent_executor.execute(app=app, version=version, inputs=inputs)

        raise ValidationError(f"Unsupported app execution: type={app.type}, schema={version.spec_schema}")
