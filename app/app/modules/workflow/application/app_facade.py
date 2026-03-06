"""app_facade

Workflow facade backed by unified apps/app_versions models.
"""

from __future__ import annotations

from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import select, and_, desc, func

from app.kernel.contracts.context import RequestContext
from app.kernel.commons.errors import ValidationError, NotFoundError
from app.kernel.identity.guard import rbac_guard, workspace_guard
from app.kernel.identity.permissions import RESOURCE_WORKFLOW
from app.kernel.specs.validator import validate_runtime_spec
from app.kernel.contracts.execution_plan import ExecutionPlan
from app.kernel.events.bus import EventBus
from app.modules.appcenter.runtime.router import AppRuntimeRouter
from app.modules.workflow.application.compiler import WorkflowCompiler
from app.modules.workflow.application.schemas import WorkflowCreate, WorkflowUpdate, WorkflowVersionCreate
from app.modules.appcenter.application.publish_service import AppPublishService
from app.modules.appcenter.domain.models import App, AppVersion
from app.modules.appcenter.application.ports import AppRepositoryPort, AppVersionRepositoryPort


class WorkflowAppFacadeService:
    """Workflow facade that uses apps/app_versions as the source of truth."""

    def __init__(
        self,
        db: Session,
        ctx: RequestContext,
        app_repo: AppRepositoryPort,
        version_repo: AppVersionRepositoryPort,
        event_bus: Optional[EventBus] = None,
        publish_service: Optional[AppPublishService] = None,
    ):
        self.db = db
        self.ctx = ctx
        self.app_repo = app_repo
        self.version_repo = version_repo
        self.compiler = WorkflowCompiler()
        self.event_bus = event_bus
        self.runtime_router = AppRuntimeRouter(db, ctx, event_bus=event_bus)
        self.publish_service = publish_service or AppPublishService(db, ctx)

    def _resolve_workflow_create_id(self, data: WorkflowCreate, **kwargs) -> str:
        return data.name or f"new:{self.ctx.workspace_id}"

    def _resolve_default_spec(self, name: str) -> Dict[str, Any]:
        return {
            "name": name,
            "inputs_schema": {"type": "object", "properties": {}},
            "outputs_schema": {"type": "object", "properties": {"value": {"type": "object"}}},
            "graph": {
                "nodes": [
                    {"id": "t1", "type": "transform", "params": {}},
                    {"id": "o1", "type": "output", "params": {"value": "{{ steps.t1.output }}"}},
                ],
                "edges": [{"id": "e1", "from": "t1", "to": "o1"}],
            },
        }

    def _get_app(self, app_id: str) -> App:
        app = self.app_repo.get_by_id(app_id)
        if not app or app.type != "WORKFLOW":
            raise NotFoundError(f"Workflow not found: {app_id}")
        return app

    def _load_run_inputs(self, run: "Run") -> Optional[Dict[str, Any]]:
        if not run.input_summary:
            return None
        import json
        try:
            parsed = json.loads(run.input_summary)
            if isinstance(parsed, dict):
                return parsed
            return None
        except Exception:
            return None

    def _get_run_record(self, app_id: str, run_id: str) -> "Run":
        from app.kernel.trace.models import Run

        query = select(Run).where(
            and_(
                Run.id == run_id,
                Run.tenant_id == self.ctx.tenant_id,
                Run.workspace_id == self.ctx.workspace_id,
                Run.app_id == app_id,
                Run.mode == "workflow",
            )
        )
        run = self.db.exec(query).first()
        if run and not hasattr(run, "status"):
            run = run[0]
        if not run:
            raise NotFoundError(f"Run not found: {run_id}")
        return run

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

    @rbac_guard(RESOURCE_WORKFLOW, "create", resource_id_resolver=_resolve_workflow_create_id)
    async def create_workflow(self, data: WorkflowCreate) -> App:
        query = select(App).where(
            and_(
                App.tenant_id == self.ctx.tenant_id,
                App.workspace_id == self.ctx.workspace_id,
                App.type == "WORKFLOW",
                App.name == data.name,
            )
        )
        existing = self.db.exec(query).first()
        if existing:
            raise ValidationError(f"Workflow with name '{data.name}' already exists")

        app = App(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            type="WORKFLOW",
            status="active",
            visibility="private",
            name=data.name,
            description=data.description,
            created_by=self.ctx.user_id,
        )
        app = self.app_repo.create(app)

        spec_json = self._resolve_default_spec(data.name)
        version = AppVersion(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            app_id=app.id,
            version=self._next_version_number(app.id),
            status="draft",
            spec_schema="workflow.v1",
            spec_json=spec_json,
            created_by=self.ctx.user_id,
        )
        version = self.version_repo.create(version)
        app.current_version_id = version.id
        self.app_repo.update(app)
        return app

    @rbac_guard(RESOURCE_WORKFLOW, "update", resource_id_arg="app_id")
    async def update_workflow(self, app_id: str, data: WorkflowUpdate) -> App:
        app = self._get_app(app_id)

        if data.name and data.name != app.name:
            query = select(App).where(
                and_(
                    App.tenant_id == self.ctx.tenant_id,
                    App.workspace_id == self.ctx.workspace_id,
                    App.type == "WORKFLOW",
                    App.name == data.name,
                    App.id != app_id,
                )
            )
            existing = self.db.exec(query).first()
            if existing:
                raise ValidationError(f"Workflow with name '{data.name}' already exists")
            app.name = data.name

        if data.description is not None:
            app.description = data.description
        if data.metadata_json is not None:
            app.metadata_json = data.metadata_json

        from app.kernel.commons.time import utc_now
        app.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(app)
        return app

    @rbac_guard(RESOURCE_WORKFLOW, "read", resource_id_arg="app_id")
    async def get_workflow(self, app_id: str) -> App:
        return self._get_app(app_id)

    @workspace_guard("read")
    async def list_workflows(self, limit: int = 20, offset: int = 0) -> List[App]:
        query = select(App).where(
            and_(
                App.tenant_id == self.ctx.tenant_id,
                App.workspace_id == self.ctx.workspace_id,
                App.type == "WORKFLOW",
                App.status != "archived",
            )
        ).order_by(desc(App.created_at)).offset(offset).limit(limit)
        results = list(self.db.exec(query).all())
        if not results:
            return []
        if isinstance(results[0], App):
            return results
        return [row[0] for row in results if row]

    @rbac_guard(RESOURCE_WORKFLOW, "delete", resource_id_arg="app_id")
    async def delete_workflow(self, app_id: str) -> None:
        app = self._get_app(app_id)
        from app.kernel.commons.time import utc_now

        app.status = "archived"
        app.updated_at = utc_now()
        self.db.commit()

    def validate_spec(self, graph_json: dict) -> None:
        try:
            validate_runtime_spec("workflow.v1", graph_json, raise_on_error=True)
            self.compiler.compile(graph_json, {}, "dummy_run_id")
        except Exception as exc:
            raise ValidationError(f"Invalid workflow spec: {str(exc)}")

    @rbac_guard(RESOURCE_WORKFLOW, "update", resource_id_arg="app_id")
    async def publish_version(self, app_id: str, data: WorkflowVersionCreate) -> AppVersion:
        app = self._get_app(app_id)
        self.validate_spec(data.graph_json)

        version = AppVersion(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            app_id=app_id,
            version=self._next_version_number(app_id),
            status="draft",
            spec_schema="workflow.v1",
            spec_json=data.graph_json,
            created_by=data.created_by,
        )
        version = self.version_repo.create(version)
        published = self.publish_service.publish(app_id, version.id, run_preflight=data.preflight)
        return published

    @rbac_guard(RESOURCE_WORKFLOW, "read", resource_id_arg="app_id")
    async def get_current_version(self, app_id: str) -> Optional[AppVersion]:
        app = self._get_app(app_id)
        if not app.current_version_id:
            return None
        version = self.version_repo.get_by_id(app.current_version_id)
        if version and version.app_id == app_id:
            return version
        return None

    @rbac_guard(RESOURCE_WORKFLOW, "read", resource_id_arg="app_id")
    async def list_versions(self, app_id: str, limit: int = 20, offset: int = 0) -> List[AppVersion]:
        self._get_app(app_id)
        query = select(AppVersion).where(
            and_(
                AppVersion.app_id == app_id,
                AppVersion.tenant_id == self.ctx.tenant_id,
                AppVersion.workspace_id == self.ctx.workspace_id,
            )
        ).order_by(desc(AppVersion.created_at)).offset(offset).limit(limit)
        results = list(self.db.exec(query).all())
        return [item if isinstance(item, AppVersion) else item[0] for item in results]

    @rbac_guard(RESOURCE_WORKFLOW, "update", resource_id_arg="app_id")
    async def rollback_version(self, app_id: str, version_id: str, *, run_preflight: bool = False) -> App:
        app = self._get_app(app_id)
        version = self.version_repo.get_by_id(version_id)
        if not version or version.app_id != app_id:
            raise NotFoundError(f"Version not found: {version_id}")
        self.publish_service.publish(app_id, version_id, run_preflight=run_preflight)
        self.db.refresh(app)
        return app

    @rbac_guard(RESOURCE_WORKFLOW, "read", resource_id_arg="app_id")
    async def compile_workflow(
        self,
        app_id: str,
        inputs: dict,
        run_id: str,
    ) -> ExecutionPlan:
        version = await self.get_current_version(app_id)
        if not version:
            raise NotFoundError(f"No published version for workflow: {app_id}")

        plan = self.compiler.compile(version.spec_json, inputs, run_id)
        plan.app_id = app_id
        plan.app_version_id = version.id
        return plan

    @rbac_guard(RESOURCE_WORKFLOW, "run", resource_id_arg="app_id")
    async def execute_workflow(self, app_id: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        return await self.runtime_router.execute(
            app_id=app_id,
            inputs=inputs,
            use_current=True,
        )

    @rbac_guard(RESOURCE_WORKFLOW, "read", resource_id_arg="app_id")
    @rbac_guard(RESOURCE_WORKFLOW, "run", resource_id_arg="app_id")
    async def pause_run(self, app_id: str, run_id: str) -> dict:
        run = self._get_run_record(app_id, run_id)
        if run.status != "running":
            raise ValidationError("Only running runs can be paused")
        from app.kernel.trace.writer import TraceWriter

        trace_writer = TraceWriter(self.db, self.ctx, event_bus=self.event_bus)
        trace_writer.update_run_status(run.id, "paused")
        return {"run_id": run.id, "status": "paused"}

    @rbac_guard(RESOURCE_WORKFLOW, "run", resource_id_arg="app_id")
    async def resume_run(self, app_id: str, run_id: str) -> dict:
        run = self._get_run_record(app_id, run_id)
        if run.status != "paused":
            raise ValidationError("Only paused runs can be resumed")
        from app.kernel.trace.writer import TraceWriter

        trace_writer = TraceWriter(self.db, self.ctx, event_bus=self.event_bus)
        trace_writer.update_run_status(run.id, "running")
        return {"run_id": run.id, "status": "running"}

    @rbac_guard(RESOURCE_WORKFLOW, "run", resource_id_arg="app_id")
    async def retry_run(
        self,
        app_id: str,
        run_id: str,
        inputs: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        run = self._get_run_record(app_id, run_id)
        if run.status not in ("failed", "canceled"):
            raise ValidationError("Only failed or canceled runs can be retried")
        payload = inputs or self._load_run_inputs(run)
        if payload is None:
            raise ValidationError("Retry requires inputs or a parseable run input_summary")
        return await self.execute_workflow(app_id, payload)

    @rbac_guard(RESOURCE_WORKFLOW, "run", resource_id_arg="app_id")
    async def replay_run(
        self,
        app_id: str,
        run_id: str,
        inputs: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        run = self._get_run_record(app_id, run_id)
        payload = inputs or self._load_run_inputs(run)
        if payload is None:
            raise ValidationError("Replay requires inputs or a parseable run input_summary")
        return await self.execute_workflow(app_id, payload)

    @rbac_guard(RESOURCE_WORKFLOW, "read", resource_id_arg="app_id")
    async def export_dsl(
        self,
        app_id: str,
        *,
        version_id: Optional[str] = None,
        format: str = "json",
    ) -> Dict[str, Any]:
        version = None
        if version_id:
            version = self.version_repo.get_by_id(version_id)
            if not version or version.app_id != app_id:
                raise NotFoundError(f"Version not found: {version_id}")
        else:
            version = await self.get_current_version(app_id)
        if not version:
            raise NotFoundError(f"No published version for workflow: {app_id}")
        normalized = (format or "json").lower()
        if normalized not in ("json", "yaml"):
            raise ValidationError("Unsupported DSL format")
        payload = version.spec_json
        if normalized == "yaml":
            import yaml
            payload = yaml.safe_dump(payload, sort_keys=False)
        return {"format": normalized, "dsl": payload}

    @rbac_guard(RESOURCE_WORKFLOW, "update", resource_id_arg="app_id")
    async def import_dsl(
        self,
        app_id: str,
        dsl: Any,
        created_by: str,
        *,
        format: str = "json",
    ) -> AppVersion:
        normalized = (format or "json").lower()
        if normalized not in ("json", "yaml"):
            raise ValidationError("Unsupported DSL format")
        payload = dsl
        if isinstance(payload, str):
            if normalized == "yaml":
                import yaml
                payload = yaml.safe_load(payload) or {}
            else:
                import json
                payload = json.loads(payload)
        if not isinstance(payload, dict):
            raise ValidationError("Workflow DSL must be an object")
        self.validate_spec(payload)
        self._get_app(app_id)

        version = AppVersion(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            app_id=app_id,
            version=self._next_version_number(app_id),
            status="published",
            spec_schema="workflow.v1",
            spec_json=payload,
            created_by=created_by,
        )
        version = self.version_repo.create(version)
        from app.kernel.commons.time import utc_now

        app = self._get_app(app_id)
        app.current_version_id = version.id
        app.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(app)
        return version
