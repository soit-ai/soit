"""Workflow application service backed by dedicated workflow tables."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC
from typing import Any

from sqlalchemy import and_, desc, select
from sqlalchemy.orm import Session

from app.kernel.commons.errors import NotFoundError, ValidationError
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.contracts.execution_plan import ExecutionPlan
from app.kernel.contracts.pagination import PageToken
from app.kernel.events.bus import EventBus
from app.kernel.identity.guard import rbac_guard, workspace_guard
from app.kernel.identity.permissions import RESOURCE_WORKFLOW
from app.kernel.runtime.db.models.runs import Run
from app.kernel.runtime.responses.service import ResponseService
from app.kernel.runtime.runs.writer import TraceWriter
from app.kernel.specs.validator import validate_runtime_spec
from app.modules.versioning.application.service import VersionControlService
from app.modules.workflow.application.compiler import WorkflowCompiler
from app.modules.workflow.application.schemas import (
    WorkflowCreate,
    WorkflowUpdate,
    WorkflowVersionCreate,
    WorkflowWorkbenchItemsResponse,
    WorkflowWorkbenchResponse,
    WorkflowWorkbenchRow,
    WorkflowWorkbenchSummary,
    WorkflowWorkbenchTabs,
)
from app.modules.workflow.application.versioning_adapter import (
    WorkflowVersioningAdapter,
)
from app.modules.workflow.domain.models import (
    Workflow,
    WorkflowPublish,
    WorkflowVersion,
)
from app.modules.workflow.infra.repository import (
    WorkflowPublishRepository,
    WorkflowRepository,
    WorkflowVersionRepository,
)
from app.modules.workflow.runtime.engine import ExecutionEngine
from app.modules.workflow.templates.ticket_triage import build_ticket_triage_template


class WorkflowService:
    """Workflow aggregate service."""

    def __init__(
        self,
        db: Session,
        ctx: RequestContext,
        workflow_repo: WorkflowRepository | None = None,
        version_repo: WorkflowVersionRepository | None = None,
        event_bus: EventBus | None = None,
        publish_repo: WorkflowPublishRepository | None = None,
        response_service: ResponseService | None = None,
        approval_checkpoint_gateway: Any | None = None,
        **_: Any,
    ):
        self.db = db
        self.ctx = ctx
        self.workflow_repo = workflow_repo if isinstance(workflow_repo, WorkflowRepository) else WorkflowRepository(db, ctx)
        self.version_repo = version_repo if isinstance(version_repo, WorkflowVersionRepository) else WorkflowVersionRepository(db, ctx)
        self.compiler = WorkflowCompiler()
        self.event_bus = event_bus
        self.publish_repo = publish_repo or WorkflowPublishRepository(db, ctx)
        self.trace_writer = TraceWriter(db, ctx, event_bus=event_bus)
        self.response_service = response_service
        self.versioning = VersionControlService(
            WorkflowVersioningAdapter(
                workflow_repo=self.workflow_repo,
                version_repo=self.version_repo,
                publish_repo=self.publish_repo,
                validate_spec=self.validate_spec,
            ),
            ctx=ctx,
            approval_checkpoint_gateway=approval_checkpoint_gateway,
        )
        self.engine = ExecutionEngine(
            db,
            ctx,
            trace_writer=self.trace_writer,
            response_service=self.response_service,
        )

    def _resolve_workflow_create_id(self, data: WorkflowCreate, **kwargs) -> str:
        return data.name or f"new:{self.ctx.workspace_id}"

    def _resolve_ticket_template_create_id(self, name: str = "Ticket triage", **kwargs) -> str:
        return name or "Ticket triage"

    def _resolve_default_spec(self, name: str) -> dict[str, Any]:
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

    def _get_workflow(self, workflow_id: str) -> Workflow:
        workflow = self.workflow_repo.get_by_id(workflow_id)
        if not workflow:
            raise NotFoundError(f"Workflow not found: {workflow_id}")
        return workflow

    def _load_run_inputs(self, run: Run) -> dict[str, Any] | None:
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

    def _get_run_record(self, workflow_id: str, run_id: str) -> Run:
        from app.kernel.runtime.db.models.runs import Run

        query = select(Run).where(
            and_(
                Run.id == run_id,
                Run.tenant_id == self.ctx.tenant_id,
                Run.workspace_id == self.ctx.workspace_id,
                Run.mode == "workflow",
            )
        )
        run = self.db.exec(query).first()
        if run and not hasattr(run, "status"):
            run = run[0]
        if not run:
            raise NotFoundError(f"Run not found: {run_id}")
        if run.subject_kind == "workflow" and run.subject_id == workflow_id:
            return run
        raise NotFoundError(f"Run not found: {run_id}")

    async def _create_workflow_with_initial_spec(
        self,
        data: WorkflowCreate,
        spec_json: dict[str, Any],
        *,
        metadata_json: dict[str, Any] | None = None,
    ) -> Workflow:
        existing = self.workflow_repo.get_by_name(data.name)
        if existing:
            raise ValidationError(f"Workflow with name '{data.name}' already exists")

        workflow = Workflow(
            status="active",
            visibility=data.visibility,
            name=data.name,
            description=data.description,
            summary=data.summary,
            icon_url=data.icon_url,
            category=data.category,
            tags=data.tags,
            owner_user_id=self.ctx.user_id,
            metadata_json=metadata_json or {},
            created_by=self.ctx.user_id,
        )
        workflow = self.workflow_repo.create(workflow)

        await self.create_version(
            workflow.id,
            WorkflowVersionCreate(
                graph_json=spec_json,
                created_by=self.ctx.user_id or "",
            ),
        )
        return self._get_workflow(workflow.id)

    @rbac_guard(RESOURCE_WORKFLOW, "create", resource_id_resolver=_resolve_workflow_create_id)
    async def create_workflow(self, data: WorkflowCreate) -> Workflow:
        return await self._create_workflow_with_initial_spec(
            data,
            self._resolve_default_spec(data.name),
        )

    @rbac_guard(RESOURCE_WORKFLOW, "create", resource_id_resolver=_resolve_ticket_template_create_id)
    async def create_ticket_triage_template(self, name: str = "Ticket triage") -> Workflow:
        spec_json = build_ticket_triage_template()
        spec_json["name"] = name
        return await self._create_workflow_with_initial_spec(
            WorkflowCreate(
                name=name,
                description="Ticket triage workflow template",
                summary="Classifies a support request, creates a governed review ticket, and returns citations.",
                category="support",
                tags=["template", "ticket-triage"],
            ),
            spec_json,
            metadata_json={"template_key": "ticket_triage"},
        )

    @rbac_guard(RESOURCE_WORKFLOW, "update", resource_id_arg="workflow_id")
    async def update_workflow(self, workflow_id: str, data: WorkflowUpdate) -> Workflow:
        workflow = self._get_workflow(workflow_id)

        if data.name and data.name != workflow.name:
            existing = self.workflow_repo.get_by_name(data.name)
            if existing:
                raise ValidationError(f"Workflow with name '{data.name}' already exists")
            workflow.name = data.name

        if data.description is not None:
            workflow.description = data.description
        if data.summary is not None:
            workflow.summary = data.summary
        if data.status is not None:
            workflow.status = data.status
        if data.visibility is not None:
            workflow.visibility = data.visibility
        if data.icon_url is not None:
            workflow.icon_url = data.icon_url
        if data.category is not None:
            workflow.category = data.category
        if data.tags is not None:
            workflow.tags = data.tags
        if data.metadata_json is not None:
            workflow.metadata_json = data.metadata_json

        return self.workflow_repo.update(workflow)

    @rbac_guard(RESOURCE_WORKFLOW, "read", resource_id_arg="workflow_id")
    async def get_workflow(self, workflow_id: str) -> Workflow:
        return self._get_workflow(workflow_id)

    @workspace_guard("read")
    async def list_workflows(self, limit: int = 20, offset: int = 0) -> list[Workflow]:
        return self.workflow_repo.list(limit=limit, offset=offset)

    @workspace_guard("read")
    async def get_workbench(self, limit: int = 20, offset: int = 0) -> WorkflowWorkbenchResponse:
        rows, runs_by_workflow = self._build_workbench_rows()
        all_today_runs = [
            run
            for workflow_runs in runs_by_workflow.values()
            for run in workflow_runs
            if self._is_today(run.started_at)
        ]
        summary = WorkflowWorkbenchSummary(
            total_workflows=len(rows),
            published_workflows=sum(1 for row in rows if row.action_enabled),
            running_workflows=sum(1 for row in rows if row.action_enabled),
            today_runs=len(all_today_runs),
            avg_latency_ms=self._average_latency(all_today_runs),
            success_rate=self._success_rate(all_today_runs),
            recent_exceptions=sum(1 for run in all_today_runs if self._run_failed(run)),
            updated_at=utc_now(),
        )
        tabs = WorkflowWorkbenchTabs(
            all=len(rows),
            high_volume=sum(1 for row in rows if row.today_runs >= 100),
            publishing=sum(1 for row in rows if row.status == "publishing"),
            abnormal=sum(1 for row in rows if row.status == "abnormal"),
            draft=sum(1 for row in rows if row.status == "draft"),
        )
        visible_rows = rows[offset: offset + limit]
        has_next = offset + len(visible_rows) < len(rows)
        next_page_token = PageToken(offset=offset + len(visible_rows), limit=limit).to_string() if has_next else None
        return WorkflowWorkbenchResponse(
            summary=summary,
            tabs=tabs,
            items=visible_rows,
            next_page_token=next_page_token,
            page_size=len(visible_rows),
        )

    @workspace_guard("read")
    async def get_workbench_items(
        self,
        limit: int = 20,
        offset: int = 0,
        tab: str | None = None,
        keyword: str | None = None,
    ) -> WorkflowWorkbenchItemsResponse:
        rows, _ = self._build_workbench_rows()
        filtered_rows = self._filter_workbench_rows(rows, tab=tab, keyword=keyword)
        visible_rows = filtered_rows[offset: offset + limit]
        has_next = offset + len(visible_rows) < len(filtered_rows)
        next_page_token = PageToken(offset=offset + len(visible_rows), limit=limit).to_string() if has_next else None
        return WorkflowWorkbenchItemsResponse(
            items=visible_rows,
            next_page_token=next_page_token,
            page_size=len(visible_rows),
        )

    def _build_workbench_rows(self) -> tuple[list[WorkflowWorkbenchRow], dict[str, list[Run]]]:
        workflows = self._list_workbench_workflows()
        workflow_ids = [workflow.id for workflow in workflows]
        runs_by_workflow = self._workbench_runs_by_workflow(workflow_ids)
        rows = [
            self._build_workbench_row(workflow, runs_by_workflow.get(workflow.id, []))
            for workflow in workflows
        ]
        return rows, runs_by_workflow

    def _filter_workbench_rows(
        self,
        rows: list[WorkflowWorkbenchRow],
        *,
        tab: str | None,
        keyword: str | None,
    ) -> list[WorkflowWorkbenchRow]:
        normalized_tab = (tab or "all").strip().lower()
        normalized_keyword = (keyword or "").strip().lower()

        def tab_matches(row: WorkflowWorkbenchRow) -> bool:
            if normalized_tab in {"", "all"}:
                return True
            if normalized_tab == "high":
                return row.today_runs >= 100
            return row.status == normalized_tab

        def keyword_matches(row: WorkflowWorkbenchRow) -> bool:
            if not normalized_keyword:
                return True
            haystack = " ".join(
                filter(
                    None,
                    [
                        row.name,
                        row.description,
                        row.summary,
                        row.owner,
                        row.status,
                        " ".join(row.linked_agents),
                    ],
                )
            ).lower()
            return normalized_keyword in haystack

        return [row for row in rows if tab_matches(row) and keyword_matches(row)]

    def _list_workbench_workflows(self) -> list[Workflow]:
        query = (
            select(Workflow)
            .where(
                and_(
                    Workflow.tenant_id == self.ctx.tenant_id,
                    Workflow.workspace_id == self.ctx.workspace_id,
                    Workflow.deleted_at.is_(None),
                )
            )
            .order_by(desc(Workflow.updated_at))
        )
        results = list(self.db.exec(query).all())
        return [item if isinstance(item, Workflow) else item[0] for item in results]

    def _workbench_runs_by_workflow(self, workflow_ids: list[str]) -> dict[str, list[Run]]:
        if not workflow_ids:
            return {}
        query = (
            select(Run)
            .where(
                and_(
                    Run.tenant_id == self.ctx.tenant_id,
                    Run.workspace_id == self.ctx.workspace_id,
                    Run.subject_kind == "workflow",
                    Run.subject_id.in_(workflow_ids),
                )
            )
            .order_by(desc(Run.started_at))
        )
        results = list(self.db.exec(query).all())
        grouped: dict[str, list[Run]] = defaultdict(list)
        for item in results:
            run = item if isinstance(item, Run) else item[0]
            if run.subject_id:
                grouped[run.subject_id].append(run)
        return grouped

    def _build_workbench_row(self, workflow: Workflow, runs: list[Run]) -> WorkflowWorkbenchRow:
        today_runs = [run for run in runs if self._is_today(run.started_at)]
        metric_runs = today_runs if today_runs else runs
        avg_latency_ms = self._average_latency(metric_runs)
        success_rate = self._success_rate(metric_runs)
        exception_count = sum(1 for run in metric_runs if self._run_failed(run))
        linked_agents = self._linked_agent_initials(workflow)
        return WorkflowWorkbenchRow(
            id=workflow.id,
            name=workflow.name,
            description=workflow.description,
            summary=workflow.summary,
            status=self._resolve_workbench_status(workflow, exception_count, success_rate),
            linked_agents=linked_agents,
            linked_agent_count=len(linked_agents),
            today_runs=len(today_runs),
            avg_latency_ms=avg_latency_ms,
            success_rate=success_rate,
            recent_exception_count=exception_count,
            owner=workflow.owner_user_id or workflow.updated_by or workflow.created_by,
            last_run_at=runs[0].started_at if runs else None,
            action_enabled=workflow.status == "active" and bool(workflow.published_version_id),
            updated_at=workflow.updated_at,
        )

    def _resolve_workbench_status(
        self,
        workflow: Workflow,
        exception_count: int,
        success_rate: float | None,
    ) -> str:
        if not workflow.published_version_id:
            return "draft"
        if workflow.status != "active":
            return "publishing"
        if exception_count > 0 or (success_rate is not None and success_rate < 95):
            return "abnormal"
        return "running"

    def _linked_agent_initials(self, workflow: Workflow) -> list[str]:
        raw_agents = (workflow.metadata_json or {}).get("linked_agents") if isinstance(workflow.metadata_json, dict) else None
        if not isinstance(raw_agents, list):
            return []
        initials: list[str] = []
        for value in raw_agents:
            if not isinstance(value, str) or not value.strip():
                continue
            parts = value.replace("_", " ").replace("-", " ").split()
            if len(parts) >= 2:
                initials.append((parts[0][:1] + parts[1][:1]).upper())
            else:
                initials.append(value[:2].upper())
        return initials[:4]

    def _is_today(self, value) -> bool:
        if value is None:
            return False
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        start = utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
        return value >= start

    def _average_latency(self, runs: list[Run]) -> int | None:
        durations = [run.duration_ms for run in runs if run.duration_ms is not None]
        if not durations:
            return None
        return int(round(sum(durations) / len(durations)))

    def _success_rate(self, runs: list[Run]) -> float | None:
        if not runs:
            return None
        successes = sum(1 for run in runs if run.status in {"succeeded", "completed"})
        return round((successes / len(runs)) * 100, 1)

    def _run_failed(self, run: Run) -> bool:
        return run.status == "failed" or bool(run.error_message)

    @rbac_guard(RESOURCE_WORKFLOW, "delete", resource_id_arg="workflow_id")
    async def delete_workflow(self, workflow_id: str) -> None:
        workflow = self._get_workflow(workflow_id)
        workflow.status = "archived"
        workflow.deleted_at = utc_now()
        self.workflow_repo.update(workflow)

    def validate_spec(self, graph_json: dict) -> None:
        try:
            validate_runtime_spec("workflow.v1", graph_json, raise_on_error=True)
            self.compiler.compile(graph_json, {}, "dummy_run_id")
        except Exception as exc:
            raise ValidationError(f"Invalid workflow spec: {str(exc)}")

    @rbac_guard(RESOURCE_WORKFLOW, "update", resource_id_arg="workflow_id")
    async def create_version(self, workflow_id: str, data: WorkflowVersionCreate) -> WorkflowVersion:
        return self.versioning.create_draft(
            workflow_id,
            spec_schema="workflow.v1",
            spec_json=data.graph_json,
            metadata={"created_by": data.created_by},
        )

    @rbac_guard(RESOURCE_WORKFLOW, "update", resource_id_arg="workflow_id")
    async def publish_version(
        self,
        workflow_id: str,
        version_id: str,
        *,
        run_preflight: bool = False,
        notes: str | None = None,
    ) -> Workflow:
        return self.versioning.publish(workflow_id, version_id, notes=notes)

    @rbac_guard(RESOURCE_WORKFLOW, "read", resource_id_arg="workflow_id")
    async def get_current_version(self, workflow_id: str) -> WorkflowVersion | None:
        return self.versioning.get_head_version(workflow_id)

    @rbac_guard(RESOURCE_WORKFLOW, "read", resource_id_arg="workflow_id")
    async def get_live_version(self, workflow_id: str) -> WorkflowVersion | None:
        return self.versioning.get_live_version(workflow_id)

    @rbac_guard(RESOURCE_WORKFLOW, "read", resource_id_arg="workflow_id")
    async def list_versions(self, workflow_id: str, limit: int = 20, offset: int = 0) -> list[WorkflowVersion]:
        return self.versioning.list_versions(workflow_id, limit=limit, offset=offset)

    @rbac_guard(RESOURCE_WORKFLOW, "read", resource_id_arg="workflow_id")
    async def list_releases(self, workflow_id: str, limit: int = 20, offset: int = 0) -> list[WorkflowPublish]:
        return self.versioning.list_releases(workflow_id, limit=limit, offset=offset)

    @rbac_guard(RESOURCE_WORKFLOW, "update", resource_id_arg="workflow_id")
    async def rollback_version(
        self,
        workflow_id: str,
        version_id: str,
        *,
        run_preflight: bool = False,
        notes: str | None = None,
    ) -> Workflow:
        return self.versioning.rollback(workflow_id, version_id, notes=notes)

    @rbac_guard(RESOURCE_WORKFLOW, "read", resource_id_arg="workflow_id")
    async def compile_workflow(
        self,
        workflow_id: str,
        inputs: dict,
        run_id: str,
    ) -> ExecutionPlan:
        version = await self.get_live_version(workflow_id)
        if not version:
            raise NotFoundError(f"No published version for workflow: {workflow_id}")

        plan = self.compiler.compile(version.spec_json, inputs, run_id)
        plan.subject_kind = "workflow"
        plan.subject_id = workflow_id
        plan.subject_version_id = version.id
        return plan

    @rbac_guard(RESOURCE_WORKFLOW, "run", resource_id_arg="workflow_id")
    async def execute_workflow(self, workflow_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
        plan = await self.compile_workflow(workflow_id, inputs, run_id="")
        result = await self.engine.execute(plan)
        return {"run_id": plan.run_id, "output": result}

    @rbac_guard(RESOURCE_WORKFLOW, "read", resource_id_arg="workflow_id")
    @rbac_guard(RESOURCE_WORKFLOW, "run", resource_id_arg="workflow_id")
    async def pause_run(self, workflow_id: str, run_id: str) -> dict:
        run = self._get_run_record(workflow_id, run_id)
        if run.status != "running":
            raise ValidationError("Only running runs can be paused")
        self.trace_writer.update_run_status(run.id, "paused")
        return {"run_id": run.id, "status": "paused"}

    @rbac_guard(RESOURCE_WORKFLOW, "run", resource_id_arg="workflow_id")
    async def resume_run(self, workflow_id: str, run_id: str) -> dict:
        run = self._get_run_record(workflow_id, run_id)
        if run.status != "paused":
            raise ValidationError("Only paused runs can be resumed")
        self.trace_writer.update_run_status(run.id, "running")
        return {"run_id": run.id, "status": "running"}

    @rbac_guard(RESOURCE_WORKFLOW, "run", resource_id_arg="workflow_id")
    async def cancel_run(
        self,
        workflow_id: str,
        run_id: str,
        reason: str | None = None,
    ) -> dict:
        run = self._get_run_record(workflow_id, run_id)
        if run.status not in ("queued", "running", "paused"):
            raise ValidationError("Only queued, running, or paused runs can be canceled")
        message = reason or "Workflow run canceled by user"
        self.trace_writer.update_run_status(
            run.id,
            "canceled",
            output_summary=message,
            error_code="workflow_run_canceled",
            error_message=message,
        )
        return {"run_id": run.id, "status": "canceled"}

    @rbac_guard(RESOURCE_WORKFLOW, "run", resource_id_arg="workflow_id")
    async def fail_run(
        self,
        workflow_id: str,
        run_id: str,
        *,
        error_code: str = "workflow_run_failed",
        error_message: str | None = None,
    ) -> dict:
        run = self._get_run_record(workflow_id, run_id)
        if run.status not in ("queued", "running", "paused"):
            raise ValidationError("Only queued, running, or paused runs can be marked failed")
        message = error_message or "Workflow run marked failed by user"
        self.trace_writer.update_run_status(
            run.id,
            "failed",
            output_summary=message,
            error_code=error_code or "workflow_run_failed",
            error_message=message,
        )
        return {"run_id": run.id, "status": "failed"}

    @rbac_guard(RESOURCE_WORKFLOW, "run", resource_id_arg="workflow_id")
    async def retry_run(
        self,
        workflow_id: str,
        run_id: str,
        inputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        run = self._get_run_record(workflow_id, run_id)
        if run.status not in ("failed", "canceled"):
            raise ValidationError("Only failed or canceled runs can be retried")
        payload = inputs or self._load_run_inputs(run)
        if payload is None:
            raise ValidationError("Retry requires inputs or a parseable run input_summary")
        result = await self.execute_workflow(workflow_id, payload)
        result["source_run_id"] = run.id
        result["control_action"] = "retry"
        return result

    @rbac_guard(RESOURCE_WORKFLOW, "run", resource_id_arg="workflow_id")
    async def replay_run(
        self,
        workflow_id: str,
        run_id: str,
        inputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        run = self._get_run_record(workflow_id, run_id)
        payload = inputs or self._load_run_inputs(run)
        if payload is None:
            raise ValidationError("Replay requires inputs or a parseable run input_summary")
        result = await self.execute_workflow(workflow_id, payload)
        result["source_run_id"] = run.id
        result["control_action"] = "replay"
        return result

    @rbac_guard(RESOURCE_WORKFLOW, "read", resource_id_arg="workflow_id")
    async def export_dsl(
        self,
        workflow_id: str,
        *,
        version_id: str | None = None,
        format: str = "json",
    ) -> dict[str, Any]:
        version = None
        if version_id:
            version = self.version_repo.get_by_id(version_id)
            if not version or version.workflow_id != workflow_id:
                raise NotFoundError(f"Version not found: {version_id}")
        else:
            version = await self.get_current_version(workflow_id)
        if not version:
            raise NotFoundError(f"No current version for workflow: {workflow_id}")
        normalized = (format or "json").lower()
        if normalized not in ("json", "yaml"):
            raise ValidationError("Unsupported DSL format")
        payload = version.spec_json
        if normalized == "yaml":
            import yaml
            payload = yaml.safe_dump(payload, sort_keys=False)
        return {"format": normalized, "dsl": payload}

    @rbac_guard(RESOURCE_WORKFLOW, "update", resource_id_arg="workflow_id")
    async def import_dsl(
        self,
        workflow_id: str,
        dsl: Any,
        created_by: str,
        *,
        format: str = "json",
    ) -> WorkflowVersion:
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
        return self.versioning.create_draft(
            workflow_id,
            spec_schema="workflow.v1",
            spec_json=payload,
            metadata={"created_by": created_by},
        )
