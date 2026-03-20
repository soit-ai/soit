""" service

Kernel trace query service.
"""

from typing import Optional, List, Dict, Any, Tuple
import json
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, desc, func, case

from app.kernel.contracts.context import RequestContext
from app.kernel.commons.errors import NotFoundError
from app.kernel.trace.models import Run, RunStep, RunArtifact, RunCostEntry
from app.kernel.trace.schemas import (
    RunResponse,
    RunStepResponse,
    RunStepMetricsSummaryResponse,
    RunArtifactResponse,
    RunCostEntryResponse,
    RunDetailResponse,
    RunCostSummaryResponse,
    RunCostDailyResponse,
    RunCostBySubjectResponse,
    RunCostByModeResponse,
    RunCostByProviderResponse,
    RunCostByModelResponse,
    RunAuditLogResponse,
)


class RunService:
    """Run query service for run records and cost summaries."""

    def __init__(self, db: Session, ctx: RequestContext):
        self.db = db
        self.ctx = ctx

    def list_runs(
        self,
        *,
        mode: Optional[str] = None,
        kind: Optional[str] = None,
        subject_version_id: Optional[str] = None,
        subject_version_ids: Optional[List[str]] = None,
        subject_kind: Optional[str] = None,
        subject_id: Optional[str] = None,
        status: Optional[str] = None,
        trace_id: Optional[str] = None,
        user_id: Optional[str] = None,
        started_after: Optional[datetime] = None,
        started_before: Optional[datetime] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[RunResponse]:
        """List runs with optional filters."""
        clauses = [
            Run.tenant_id == self.ctx.tenant_id,
            Run.workspace_id == self.ctx.workspace_id,
        ]
        if mode:
            clauses.append(Run.mode == mode)
        if kind:
            clauses.append(Run.kind == kind)
        if subject_kind:
            clauses.append(Run.subject_kind == subject_kind)
        if subject_id:
            clauses.append(Run.subject_id == subject_id)
        if subject_version_id:
            clauses.append(Run.subject_version_id == subject_version_id)
        if subject_version_ids:
            clauses.append(Run.subject_version_id.in_(subject_version_ids))
        if status:
            clauses.append(Run.status == status)
        if trace_id:
            clauses.append(Run.trace_id == trace_id)
        if user_id:
            clauses.append(Run.user_id == user_id)
        if started_after:
            clauses.append(Run.started_at >= started_after)
        if started_before:
            clauses.append(Run.started_at <= started_before)

        query = (
            select(Run)
            .where(and_(*clauses))
            .order_by(desc(Run.created_at))
            .offset(offset)
            .limit(limit)
        )
        rows = list(self.db.exec(query).all())
        runs = []
        for item in rows:
            if hasattr(item, "id"):
                runs.append(item)
            else:
                try:
                    runs.append(item[0])
                except Exception:
                    continue
        return [RunResponse.model_validate(run) for run in runs]

    def _build_step_clauses(
        self,
        *,
        run_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        step_id: Optional[str] = None,
        step_type: Optional[str] = None,
        status: Optional[str] = None,
        node_id: Optional[str] = None,
        started_after: Optional[datetime] = None,
        started_before: Optional[datetime] = None,
        ended_after: Optional[datetime] = None,
        ended_before: Optional[datetime] = None,
    ) -> List[Any]:
        clauses: List[Any] = [
            RunStep.tenant_id == self.ctx.tenant_id,
            RunStep.workspace_id == self.ctx.workspace_id,
        ]
        if run_id:
            clauses.append(RunStep.run_id == run_id)
        if trace_id:
            clauses.append(RunStep.trace_id == trace_id)
        if step_id:
            clauses.append(RunStep.step_id == step_id)
        if step_type:
            clauses.append(RunStep.step_type == step_type)
        if status:
            clauses.append(RunStep.status == status)
        if node_id:
            clauses.append(RunStep.node_id == node_id)
        if started_after:
            clauses.append(RunStep.started_at >= started_after)
        if started_before:
            clauses.append(RunStep.started_at <= started_before)
        if ended_after:
            clauses.append(RunStep.ended_at >= ended_after)
        if ended_before:
            clauses.append(RunStep.ended_at <= ended_before)
        return clauses

    def list_steps(
        self,
        *,
        run_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        step_id: Optional[str] = None,
        step_type: Optional[str] = None,
        status: Optional[str] = None,
        node_id: Optional[str] = None,
        started_after: Optional[datetime] = None,
        started_before: Optional[datetime] = None,
        ended_after: Optional[datetime] = None,
        ended_before: Optional[datetime] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[RunStepResponse]:
        """List run steps with optional filters."""
        clauses = self._build_step_clauses(
            run_id=run_id,
            trace_id=trace_id,
            step_id=step_id,
            step_type=step_type,
            status=status,
            node_id=node_id,
            started_after=started_after,
            started_before=started_before,
            ended_after=ended_after,
            ended_before=ended_before,
        )
        query = (
            select(RunStep)
            .where(and_(*clauses))
            .order_by(desc(RunStep.created_at))
            .offset(offset)
            .limit(limit)
        )
        rows = list(self.db.exec(query).all())
        steps = []
        for item in rows:
            if hasattr(item, "id"):
                steps.append(item)
            else:
                try:
                    steps.append(item[0])
                except Exception:
                    continue
        return [RunStepResponse.model_validate(step) for step in steps]

    def summarize_step_metrics(
        self,
        *,
        run_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        step_id: Optional[str] = None,
        step_type: Optional[str] = None,
        status: Optional[str] = None,
        node_id: Optional[str] = None,
        started_after: Optional[datetime] = None,
        started_before: Optional[datetime] = None,
        ended_after: Optional[datetime] = None,
        ended_before: Optional[datetime] = None,
    ) -> List[RunStepMetricsSummaryResponse]:
        """Aggregate step metrics by step_type and status."""
        clauses = self._build_step_clauses(
            run_id=run_id,
            trace_id=trace_id,
            step_id=step_id,
            step_type=step_type,
            status=status,
            node_id=node_id,
            started_after=started_after,
            started_before=started_before,
            ended_after=ended_after,
            ended_before=ended_before,
        )
        query = select(RunStep).where(and_(*clauses))
        rows = list(self.db.exec(query).all())
        steps = [row if hasattr(row, "id") else row[0] for row in rows]

        summary: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for step in steps:
            key = (step.step_type, step.status)
            bucket = summary.setdefault(
                key,
                {
                    "count": 0,
                    "latency_total": 0.0,
                    "latency_count": 0,
                    "latency_min": None,
                    "latency_max": None,
                },
            )
            bucket["count"] += 1

            latency_ms = None
            metrics = step.metrics_json or {}
            if isinstance(metrics, dict) and "latency_ms" in metrics:
                latency_ms = metrics.get("latency_ms")
            if latency_ms is None and step.started_at and step.ended_at:
                delta = step.ended_at - step.started_at
                latency_ms = int(delta.total_seconds() * 1000)

            try:
                latency_val = float(latency_ms) if latency_ms is not None else None
            except (TypeError, ValueError):
                latency_val = None

            if latency_val is not None:
                bucket["latency_total"] += latency_val
                bucket["latency_count"] += 1
                bucket["latency_min"] = (
                    latency_val if bucket["latency_min"] is None else min(bucket["latency_min"], latency_val)
                )
                bucket["latency_max"] = (
                    latency_val if bucket["latency_max"] is None else max(bucket["latency_max"], latency_val)
                )

        results: List[RunStepMetricsSummaryResponse] = []
        for (step_type_val, status_val), bucket in sorted(summary.items()):
            avg_latency = None
            if bucket["latency_count"]:
                avg_latency = bucket["latency_total"] / bucket["latency_count"]
            results.append(
                RunStepMetricsSummaryResponse(
                    step_type=step_type_val,
                    status=status_val,
                    count=bucket["count"],
                    avg_latency_ms=avg_latency,
                    min_latency_ms=(
                        int(bucket["latency_min"]) if bucket["latency_min"] is not None else None
                    ),
                    max_latency_ms=(
                        int(bucket["latency_max"]) if bucket["latency_max"] is not None else None
                    ),
                )
            )
        return results

    def get_run(
        self,
        run_id: str,
        *,
        include_steps: bool = True,
        include_artifacts: bool = True,
        include_cost: bool = True,
    ) -> RunDetailResponse:
        """Get run details."""
        query = select(Run).where(
            and_(
                Run.id == run_id,
                Run.tenant_id == self.ctx.tenant_id,
                Run.workspace_id == self.ctx.workspace_id,
            )
        )
        run = self.db.exec(query).first()
        if run and not hasattr(run, "id"):
            try:
                run = run[0]
            except Exception:
                run = None
        if not run:
            raise NotFoundError(f"Run not found: {run_id}")

        steps: List[RunStepResponse] = []
        artifacts: List[RunArtifactResponse] = []
        cost_summary: Optional[RunCostSummaryResponse] = None
        cost_entries: Optional[List[RunCostEntryResponse]] = None

        if include_steps:
            steps_query = select(RunStep).where(
                and_(
                    RunStep.run_id == run_id,
                    RunStep.tenant_id == self.ctx.tenant_id,
                    RunStep.workspace_id == self.ctx.workspace_id,
                )
            ).order_by(RunStep.created_at)
            raw_steps = list(self.db.exec(steps_query).all())
            steps = [
                RunStepResponse.model_validate(item if hasattr(item, "id") else item[0])
                for item in raw_steps
            ]

        if include_artifacts:
            artifacts_query = select(RunArtifact).where(
                and_(
                    RunArtifact.run_id == run_id,
                    RunArtifact.tenant_id == self.ctx.tenant_id,
                    RunArtifact.workspace_id == self.ctx.workspace_id,
                )
            ).order_by(RunArtifact.created_at)
            raw_artifacts = list(self.db.exec(artifacts_query).all())
            artifacts = [
                RunArtifactResponse.model_validate(item if hasattr(item, "id") else item[0])
                for item in raw_artifacts
            ]

        if include_cost:
            entries_query = select(RunCostEntry).where(
                and_(
                    RunCostEntry.run_id == run_id,
                    RunCostEntry.tenant_id == self.ctx.tenant_id,
                    RunCostEntry.workspace_id == self.ctx.workspace_id,
                )
            ).order_by(RunCostEntry.created_at)
            raw_entries = list(self.db.exec(entries_query).all())
            entries = [item if hasattr(item, "id") else item[0] for item in raw_entries]
            cost_entries = [RunCostEntryResponse.model_validate(item) for item in entries]
            cost_summary = self._summarize_entries(entries)

        return RunDetailResponse(
            run=RunResponse.model_validate(run),
            steps=steps,
            artifacts=artifacts,
            cost_summary=cost_summary,
            costs=cost_entries,
        )

    def list_audits(
        self,
        *,
        run_id: str,
        step_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[RunAuditLogResponse]:
        """List audit logs derived from run steps."""
        clauses = [
            RunStep.run_id == run_id,
            RunStep.tenant_id == self.ctx.tenant_id,
            RunStep.workspace_id == self.ctx.workspace_id,
        ]
        if step_id:
            clauses.append(RunStep.id == step_id)

        query = (
            select(RunStep)
            .where(and_(*clauses))
            .order_by(desc(RunStep.created_at))
            .offset(offset)
            .limit(limit)
        )
        rows = list(self.db.exec(query).all())
        steps = [row if hasattr(row, "id") else row[0] for row in rows]

        entries: List[RunAuditLogResponse] = []
        for step in steps:
            metrics = step.metrics_json or {}
            audit_json = metrics.get("audit_json")
            audit_preview = metrics.get("audit_preview")
            audit_artifact = metrics.get("audit_artifact")
            if not audit_json and not audit_preview and not audit_artifact:
                continue

            parsed = None
            if audit_json:
                try:
                    parsed = json.loads(audit_json)
                except Exception:
                    parsed = None

            gateway_type = None
            request_payload = None
            response_payload = None
            timestamp = None
            if isinstance(parsed, dict):
                gateway_type = parsed.get("gateway_type")
                request_payload = parsed.get("request")
                response_payload = parsed.get("response")
                timestamp = parsed.get("timestamp")

            entries.append(
                RunAuditLogResponse(
                    run_id=step.run_id,
                    step_id=step.id,
                    step_type=step.step_type,
                    gateway_type=gateway_type,
                    request=request_payload,
                    response=response_payload,
                    timestamp=timestamp,
                    truncated=bool(metrics.get("audit_truncated")),
                    preview=audit_preview,
                    artifact_key=audit_artifact,
                )
            )

        return entries

    def summarize_costs(
        self,
        *,
        mode: Optional[str] = None,
        kind: Optional[str] = None,
        subject_version_id: Optional[str] = None,
        subject_version_ids: Optional[List[str]] = None,
        subject_kind: Optional[str] = None,
        subject_id: Optional[str] = None,
        status: Optional[str] = None,
        started_after: Optional[datetime] = None,
        started_before: Optional[datetime] = None,
    ) -> RunCostSummaryResponse:
        """Aggregate cost metrics for runs."""
        clauses = [
            RunCostEntry.tenant_id == self.ctx.tenant_id,
            RunCostEntry.workspace_id == self.ctx.workspace_id,
            RunCostEntry.run_id == Run.id,
            Run.tenant_id == self.ctx.tenant_id,
            Run.workspace_id == self.ctx.workspace_id,
        ]
        if mode:
            clauses.append(Run.mode == mode)
        if kind:
            clauses.append(Run.kind == kind)
        if subject_kind:
            clauses.append(Run.subject_kind == subject_kind)
        if subject_id:
            clauses.append(Run.subject_id == subject_id)
        if subject_version_id:
            clauses.append(Run.subject_version_id == subject_version_id)
        if subject_version_ids:
            clauses.append(Run.subject_version_id.in_(subject_version_ids))
        if status:
            clauses.append(Run.status == status)
        if started_after:
            clauses.append(Run.started_at >= started_after)
        if started_before:
            clauses.append(Run.started_at <= started_before)

        query = select(
            func.coalesce(func.sum(RunCostEntry.prompt_tokens), 0),
            func.coalesce(func.sum(RunCostEntry.completion_tokens), 0),
            func.coalesce(func.sum(case((RunCostEntry.unit.in_(["embeddings", "embedding"]), RunCostEntry.quantity), else_=0)), 0),
            func.coalesce(func.sum(case((RunCostEntry.unit == "rerank", RunCostEntry.quantity), else_=0)), 0),
            func.coalesce(func.sum(case((RunCostEntry.unit == "ms", RunCostEntry.quantity), else_=0)), 0),
            func.coalesce(func.sum(case((RunCostEntry.unit == "bytes", RunCostEntry.quantity), else_=0)), 0),
        ).select_from(RunCostEntry).join(Run, RunCostEntry.run_id == Run.id).where(and_(*clauses))

        row = self.db.exec(query).one()
        return RunCostSummaryResponse(
            tokens_prompt=int(row[0] or 0),
            tokens_completion=int(row[1] or 0),
            embedding_count=int(row[2] or 0),
            rerank_count=int(row[3] or 0),
            ms_total=int(row[4] or 0),
            storage_bytes=int(row[5] or 0),
        )

    def summarize_costs_by_day(
        self,
        *,
        mode: Optional[str] = None,
        kind: Optional[str] = None,
        subject_version_id: Optional[str] = None,
        subject_version_ids: Optional[List[str]] = None,
        subject_kind: Optional[str] = None,
        subject_id: Optional[str] = None,
        status: Optional[str] = None,
        started_after: Optional[datetime] = None,
        started_before: Optional[datetime] = None,
    ) -> List[RunCostDailyResponse]:
        """Aggregate cost metrics per day."""
        clauses = [
            RunCostEntry.tenant_id == self.ctx.tenant_id,
            RunCostEntry.workspace_id == self.ctx.workspace_id,
            RunCostEntry.run_id == Run.id,
            Run.tenant_id == self.ctx.tenant_id,
            Run.workspace_id == self.ctx.workspace_id,
        ]
        if mode:
            clauses.append(Run.mode == mode)
        if kind:
            clauses.append(Run.kind == kind)
        if subject_kind:
            clauses.append(Run.subject_kind == subject_kind)
        if subject_id:
            clauses.append(Run.subject_id == subject_id)
        if subject_version_id:
            clauses.append(Run.subject_version_id == subject_version_id)
        if subject_version_ids:
            clauses.append(Run.subject_version_id.in_(subject_version_ids))
        if status:
            clauses.append(Run.status == status)
        if started_after:
            clauses.append(Run.started_at >= started_after)
        if started_before:
            clauses.append(Run.started_at <= started_before)

        day_col = func.date(Run.started_at)
        query = (
            select(
                day_col.label("day"),
                func.coalesce(func.sum(RunCostEntry.prompt_tokens), 0),
                func.coalesce(func.sum(RunCostEntry.completion_tokens), 0),
                func.coalesce(func.sum(case((RunCostEntry.unit.in_(["embeddings", "embedding"]), RunCostEntry.quantity), else_=0)), 0),
                func.coalesce(func.sum(case((RunCostEntry.unit == "rerank", RunCostEntry.quantity), else_=0)), 0),
                func.coalesce(func.sum(case((RunCostEntry.unit == "ms", RunCostEntry.quantity), else_=0)), 0),
                func.coalesce(func.sum(case((RunCostEntry.unit == "bytes", RunCostEntry.quantity), else_=0)), 0),
            )
            .select_from(RunCostEntry)
            .join(Run, RunCostEntry.run_id == Run.id)
            .where(and_(*clauses))
            .group_by(day_col)
            .order_by(day_col)
        )

        rows = list(self.db.exec(query).all())
        results: List[RunCostDailyResponse] = []
        for row in rows:
            day = row[0]
            results.append(
                RunCostDailyResponse(
                    date=str(day),
                    tokens_prompt=int(row[1] or 0),
                    tokens_completion=int(row[2] or 0),
                    embedding_count=int(row[3] or 0),
                    rerank_count=int(row[4] or 0),
                    ms_total=int(row[5] or 0),
                    storage_bytes=int(row[6] or 0),
                )
            )
        return results

    def summarize_costs_by_subject(
        self,
        *,
        mode: Optional[str] = None,
        kind: Optional[str] = None,
        subject_version_ids: Optional[List[str]] = None,
        subject_kind: Optional[str] = None,
        subject_id: Optional[str] = None,
        subject_version_id: Optional[str] = None,
        status: Optional[str] = None,
        started_after: Optional[datetime] = None,
        started_before: Optional[datetime] = None,
    ) -> List[RunCostBySubjectResponse]:
        """Aggregate cost metrics per subject version."""
        clauses = [
            RunCostEntry.tenant_id == self.ctx.tenant_id,
            RunCostEntry.workspace_id == self.ctx.workspace_id,
            RunCostEntry.run_id == Run.id,
            Run.tenant_id == self.ctx.tenant_id,
            Run.workspace_id == self.ctx.workspace_id,
        ]
        if mode:
            clauses.append(Run.mode == mode)
        if kind:
            clauses.append(Run.kind == kind)
        if subject_kind:
            clauses.append(Run.subject_kind == subject_kind)
        if subject_id:
            clauses.append(Run.subject_id == subject_id)
        if subject_version_id:
            clauses.append(Run.subject_version_id == subject_version_id)
        if subject_version_ids:
            clauses.append(Run.subject_version_id.in_(subject_version_ids))
        if status:
            clauses.append(Run.status == status)
        if started_after:
            clauses.append(Run.started_at >= started_after)
        if started_before:
            clauses.append(Run.started_at <= started_before)

        query = (
            select(
                Run.subject_version_id,
                func.coalesce(func.sum(RunCostEntry.prompt_tokens), 0),
                func.coalesce(func.sum(RunCostEntry.completion_tokens), 0),
                func.coalesce(func.sum(case((RunCostEntry.unit.in_(["embeddings", "embedding"]), RunCostEntry.quantity), else_=0)), 0),
                func.coalesce(func.sum(case((RunCostEntry.unit == "rerank", RunCostEntry.quantity), else_=0)), 0),
                func.coalesce(func.sum(case((RunCostEntry.unit == "ms", RunCostEntry.quantity), else_=0)), 0),
                func.coalesce(func.sum(case((RunCostEntry.unit == "bytes", RunCostEntry.quantity), else_=0)), 0),
            )
            .select_from(RunCostEntry)
            .join(Run, RunCostEntry.run_id == Run.id)
            .where(and_(*clauses))
            .group_by(Run.subject_version_id)
            .order_by(Run.subject_version_id)
        )

        rows = list(self.db.exec(query).all())
        return [
            RunCostBySubjectResponse(
                subject_version_id=row[0],
                tokens_prompt=int(row[1] or 0),
                tokens_completion=int(row[2] or 0),
                embedding_count=int(row[3] or 0),
                rerank_count=int(row[4] or 0),
                ms_total=int(row[5] or 0),
                storage_bytes=int(row[6] or 0),
            )
            for row in rows
        ]

    def summarize_costs_by_mode(
        self,
        *,
        mode: Optional[str] = None,
        subject_version_id: Optional[str] = None,
        subject_version_ids: Optional[List[str]] = None,
        subject_kind: Optional[str] = None,
        subject_id: Optional[str] = None,
        status: Optional[str] = None,
        started_after: Optional[datetime] = None,
        started_before: Optional[datetime] = None,
        kind: Optional[str] = None,
    ) -> List[RunCostByModeResponse]:
        """Aggregate cost metrics per run mode."""
        clauses = [
            RunCostEntry.tenant_id == self.ctx.tenant_id,
            RunCostEntry.workspace_id == self.ctx.workspace_id,
            RunCostEntry.run_id == Run.id,
            Run.tenant_id == self.ctx.tenant_id,
            Run.workspace_id == self.ctx.workspace_id,
        ]
        if mode:
            clauses.append(Run.mode == mode)
        if subject_kind:
            clauses.append(Run.subject_kind == subject_kind)
        if subject_id:
            clauses.append(Run.subject_id == subject_id)
        if subject_version_id:
            clauses.append(Run.subject_version_id == subject_version_id)
        if subject_version_ids:
            clauses.append(Run.subject_version_id.in_(subject_version_ids))
        if status:
            clauses.append(Run.status == status)
        if started_after:
            clauses.append(Run.started_at >= started_after)
        if started_before:
            clauses.append(Run.started_at <= started_before)
        if kind:
            clauses.append(Run.kind == kind)

        query = (
            select(
                Run.mode,
                func.coalesce(func.sum(RunCostEntry.prompt_tokens), 0),
                func.coalesce(func.sum(RunCostEntry.completion_tokens), 0),
                func.coalesce(func.sum(case((RunCostEntry.unit.in_(["embeddings", "embedding"]), RunCostEntry.quantity), else_=0)), 0),
                func.coalesce(func.sum(case((RunCostEntry.unit == "rerank", RunCostEntry.quantity), else_=0)), 0),
                func.coalesce(func.sum(case((RunCostEntry.unit == "ms", RunCostEntry.quantity), else_=0)), 0),
                func.coalesce(func.sum(case((RunCostEntry.unit == "bytes", RunCostEntry.quantity), else_=0)), 0),
            )
            .select_from(RunCostEntry)
            .join(Run, RunCostEntry.run_id == Run.id)
            .where(and_(*clauses))
            .group_by(Run.mode)
            .order_by(Run.mode)
        )

        rows = list(self.db.exec(query).all())
        return [
            RunCostByModeResponse(
                mode=str(row[0]),
                tokens_prompt=int(row[1] or 0),
                tokens_completion=int(row[2] or 0),
                embedding_count=int(row[3] or 0),
                rerank_count=int(row[4] or 0),
                ms_total=int(row[5] or 0),
                storage_bytes=int(row[6] or 0),
            )
            for row in rows
        ]

    def summarize_costs_by_provider(
        self,
        *,
        mode: Optional[str] = None,
        kind: Optional[str] = None,
        subject_version_id: Optional[str] = None,
        subject_version_ids: Optional[List[str]] = None,
        subject_kind: Optional[str] = None,
        subject_id: Optional[str] = None,
        status: Optional[str] = None,
        started_after: Optional[datetime] = None,
        started_before: Optional[datetime] = None,
    ) -> List[RunCostByProviderResponse]:
        """Aggregate cost metrics per provider."""
        clauses = [
            RunCostEntry.tenant_id == self.ctx.tenant_id,
            RunCostEntry.workspace_id == self.ctx.workspace_id,
            RunCostEntry.run_id == Run.id,
            Run.tenant_id == self.ctx.tenant_id,
            Run.workspace_id == self.ctx.workspace_id,
        ]
        if mode:
            clauses.append(Run.mode == mode)
        if kind:
            clauses.append(Run.kind == kind)
        if subject_kind:
            clauses.append(Run.subject_kind == subject_kind)
        if subject_id:
            clauses.append(Run.subject_id == subject_id)
        if subject_version_id:
            clauses.append(Run.subject_version_id == subject_version_id)
        if subject_version_ids:
            clauses.append(Run.subject_version_id.in_(subject_version_ids))
        if status:
            clauses.append(Run.status == status)
        if started_after:
            clauses.append(Run.started_at >= started_after)
        if started_before:
            clauses.append(Run.started_at <= started_before)

        query = (
            select(
                RunCostEntry.provider,
                func.coalesce(func.sum(RunCostEntry.prompt_tokens), 0),
                func.coalesce(func.sum(RunCostEntry.completion_tokens), 0),
                func.coalesce(func.sum(case((RunCostEntry.unit.in_(["embeddings", "embedding"]), RunCostEntry.quantity), else_=0)), 0),
                func.coalesce(func.sum(case((RunCostEntry.unit == "rerank", RunCostEntry.quantity), else_=0)), 0),
                func.coalesce(func.sum(case((RunCostEntry.unit == "ms", RunCostEntry.quantity), else_=0)), 0),
                func.coalesce(func.sum(case((RunCostEntry.unit == "bytes", RunCostEntry.quantity), else_=0)), 0),
            )
            .select_from(RunCostEntry)
            .join(Run, RunCostEntry.run_id == Run.id)
            .where(and_(*clauses))
            .group_by(RunCostEntry.provider)
            .order_by(RunCostEntry.provider)
        )

        rows = list(self.db.exec(query).all())
        return [
            RunCostByProviderResponse(
                provider=row[0],
                tokens_prompt=int(row[1] or 0),
                tokens_completion=int(row[2] or 0),
                embedding_count=int(row[3] or 0),
                rerank_count=int(row[4] or 0),
                ms_total=int(row[5] or 0),
                storage_bytes=int(row[6] or 0),
            )
            for row in rows
        ]

    def summarize_costs_by_model(
        self,
        *,
        mode: Optional[str] = None,
        kind: Optional[str] = None,
        subject_version_id: Optional[str] = None,
        subject_version_ids: Optional[List[str]] = None,
        subject_kind: Optional[str] = None,
        subject_id: Optional[str] = None,
        status: Optional[str] = None,
        started_after: Optional[datetime] = None,
        started_before: Optional[datetime] = None,
    ) -> List[RunCostByModelResponse]:
        """Aggregate cost metrics per model."""
        clauses = [
            RunCostEntry.tenant_id == self.ctx.tenant_id,
            RunCostEntry.workspace_id == self.ctx.workspace_id,
            RunCostEntry.run_id == Run.id,
            Run.tenant_id == self.ctx.tenant_id,
            Run.workspace_id == self.ctx.workspace_id,
        ]
        if mode:
            clauses.append(Run.mode == mode)
        if kind:
            clauses.append(Run.kind == kind)
        if subject_kind:
            clauses.append(Run.subject_kind == subject_kind)
        if subject_id:
            clauses.append(Run.subject_id == subject_id)
        if subject_version_id:
            clauses.append(Run.subject_version_id == subject_version_id)
        if subject_version_ids:
            clauses.append(Run.subject_version_id.in_(subject_version_ids))
        if status:
            clauses.append(Run.status == status)
        if started_after:
            clauses.append(Run.started_at >= started_after)
        if started_before:
            clauses.append(Run.started_at <= started_before)

        query = (
            select(
                RunCostEntry.model_ref,
                func.coalesce(func.sum(RunCostEntry.prompt_tokens), 0),
                func.coalesce(func.sum(RunCostEntry.completion_tokens), 0),
                func.coalesce(func.sum(case((RunCostEntry.unit.in_(["embeddings", "embedding"]), RunCostEntry.quantity), else_=0)), 0),
                func.coalesce(func.sum(case((RunCostEntry.unit == "rerank", RunCostEntry.quantity), else_=0)), 0),
                func.coalesce(func.sum(case((RunCostEntry.unit == "ms", RunCostEntry.quantity), else_=0)), 0),
                func.coalesce(func.sum(case((RunCostEntry.unit == "bytes", RunCostEntry.quantity), else_=0)), 0),
            )
            .select_from(RunCostEntry)
            .join(Run, RunCostEntry.run_id == Run.id)
            .where(and_(*clauses))
            .group_by(RunCostEntry.model_ref)
            .order_by(RunCostEntry.model_ref)
        )

        rows = list(self.db.exec(query).all())
        return [
            RunCostByModelResponse(
                model_ref=row[0],
                tokens_prompt=int(row[1] or 0),
                tokens_completion=int(row[2] or 0),
                embedding_count=int(row[3] or 0),
                rerank_count=int(row[4] or 0),
                ms_total=int(row[5] or 0),
                storage_bytes=int(row[6] or 0),
            )
            for row in rows
        ]

    def _summarize_entries(self, entries: List[RunCostEntry]) -> RunCostSummaryResponse:
        tokens_prompt = 0
        tokens_completion = 0
        embedding_count = 0
        rerank_count = 0
        ms_total = 0
        storage_bytes = 0

        for entry in entries:
            if entry.prompt_tokens:
                tokens_prompt += int(entry.prompt_tokens)
            if entry.completion_tokens:
                tokens_completion += int(entry.completion_tokens)
            if entry.unit in ("embeddings", "embedding"):
                embedding_count += int(entry.quantity)
            if entry.unit == "rerank":
                rerank_count += int(entry.quantity)
            if entry.unit == "ms":
                ms_total += int(entry.quantity)
            if entry.unit == "bytes":
                storage_bytes += int(entry.quantity)

        return RunCostSummaryResponse(
            tokens_prompt=tokens_prompt,
            tokens_completion=tokens_completion,
            embedding_count=embedding_count,
            rerank_count=rerank_count,
            ms_total=ms_total,
            storage_bytes=storage_bytes,
        )
