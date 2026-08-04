"""Workspace dashboard aggregation for observe."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.kernel.commons.errors import KernelError
from app.kernel.commons.time import to_iso8601, utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.contracts.pagination import PageToken, parse_page_params
from app.kernel.runtime.db.models.responses import Response
from app.kernel.runtime.db.models.runs import (
    Run,
    RunCostEntry,
    RunStep,
    RunStepToolCall,
)
from app.kernel.runtime.runs.service import RunService
from app.kernel.runtime.status import ApprovalStatus
from app.modules.observe.application.dashboard_schemas import (
    AgentSummaryResponse,
    ApprovalsSummaryResponse,
    DashboardOverviewResponse,
    DashboardPageResponse,
    DashboardTabResponse,
    EmptyStateResponse,
    KnowledgeQualityResponse,
    MetricCardResponse,
    PriorityAlertResponse,
    RecentRunResponse,
    ToolHealthResponse,
    WorkflowBottleneckResponse,
    WorkspaceObserveDashboard,
    validate_dashboard_section_response,
)
from app.modules.observe.infra.repository import ApprovalRepository

RANGE_SECONDS = {
    "1h": 60 * 60,
    "6h": 6 * 60 * 60,
    "24h": 24 * 60 * 60,
    "7d": 7 * 24 * 60 * 60,
}

BUCKET_SECONDS = {
    "5m": 5 * 60,
    "10m": 10 * 60,
    "30m": 30 * 60,
    "1h": 60 * 60,
    "1d": 24 * 60 * 60,
}

TAB_LABELS = {
    "agent_health": "Agent Health",
    "workflow_bottlenecks": "Workflow Bottlenecks",
    "tool_reliability": "Tool Reliability",
    "knowledge_quality": "Knowledge Quality",
}

MAINLINE_RUN_MODES = {"agent", "workflow", "knowledge", "chat", "response"}


class ObserveDashboardService:
    def __init__(
        self,
        db: Session,
        ctx: RequestContext,
        approval_repo: ApprovalRepository,
    ) -> None:
        self.db = db
        self.ctx = ctx
        self.approval_repo = approval_repo

    @staticmethod
    def _duration(label: str, mapping: dict[str, int], default: str) -> timedelta:
        return timedelta(seconds=mapping.get(label, mapping[default]))

    @staticmethod
    def _normalize_tab(tab: str) -> str:
        return tab if tab in TAB_LABELS else "agent_health"

    @staticmethod
    def _rate(numerator: int | float, denominator: int | float) -> float:
        if denominator <= 0:
            return 0.0
        return round(float(numerator) / float(denominator), 4)

    @staticmethod
    def _percent(value: float) -> str:
        return f"{round(value * 100, 1)}%"

    @staticmethod
    def _status_from_failure_rate(call_count: int, failed_count: int) -> str:
        if call_count <= 0:
            return "unknown"
        failure_rate = failed_count / call_count
        if failure_rate >= 0.5:
            return "critical"
        if failure_rate > 0:
            return "warning"
        return "healthy"

    @staticmethod
    def _int_metric(metrics: dict[str, Any], key: str) -> int:
        value = metrics.get(key)
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int | float):
            return int(value)
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
        return 0

    @staticmethod
    def _float_metric(metrics: dict[str, Any], key: str) -> float | None:
        value = metrics.get(key)
        if isinstance(value, bool):
            return None
        if isinstance(value, int | float):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return None
        return None

    @staticmethod
    def _bucket_key(value: datetime, window_start: datetime, bucket: timedelta) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        if window_start.tzinfo is None:
            window_start = window_start.replace(tzinfo=UTC)
        elapsed = max(0, int((value - window_start).total_seconds()))
        bucket_seconds = max(1, int(bucket.total_seconds()))
        offset = (elapsed // bucket_seconds) * bucket_seconds
        return to_iso8601(window_start + timedelta(seconds=offset)) or ""

    def _scoped_runs(self, start: datetime, end: datetime) -> list[Run]:
        return list(
            self.db.execute(
                select(Run).where(
                    and_(
                        Run.tenant_id == self.ctx.tenant_id,
                        Run.workspace_id == self.ctx.workspace_id,
                        Run.started_at >= start,
                        Run.started_at <= end,
                    )
                )
            )
            .scalars()
            .all()
        )

    def _scoped_steps(self, start: datetime, end: datetime) -> list[RunStep]:
        return list(
            self.db.execute(
                select(RunStep).where(
                    and_(
                        RunStep.tenant_id == self.ctx.tenant_id,
                        RunStep.workspace_id == self.ctx.workspace_id,
                        RunStep.started_at >= start,
                        RunStep.started_at <= end,
                    )
                )
            )
            .scalars()
            .all()
        )

    def _scoped_costs(self, start: datetime, end: datetime) -> list[RunCostEntry]:
        return list(
            self.db.execute(
                select(RunCostEntry).where(
                    and_(
                        RunCostEntry.tenant_id == self.ctx.tenant_id,
                        RunCostEntry.workspace_id == self.ctx.workspace_id,
                        RunCostEntry.created_at >= start,
                        RunCostEntry.created_at <= end,
                    )
                )
            )
            .scalars()
            .all()
        )

    def _tool_calls_by_step(self, steps: list[RunStep]) -> dict[str, RunStepToolCall]:
        step_ids = [step.id for step in steps]
        if not step_ids:
            return {}
        records = list(
            self.db.execute(
                select(RunStepToolCall).where(
                    and_(
                        RunStepToolCall.tenant_id == self.ctx.tenant_id,
                        RunStepToolCall.workspace_id == self.ctx.workspace_id,
                        RunStepToolCall.run_step_id.in_(step_ids),
                    )
                )
            )
            .scalars()
            .all()
        )
        by_step = {record.run_step_id: record for record in records}
        missing = sorted(
            step.id
            for step in steps
            if step.step_type == "tool" and step.id not in by_step
        )
        if missing:
            raise KernelError(
                "RUNTIME_CONTRACT_VIOLATION",
                "Tool run step is missing a run_step_tool_calls record",
                {"run_step_ids": missing},
            )
        return by_step

    def _responses_for_runs(self, run_ids: list[str]) -> list[Response]:
        if not run_ids:
            return []
        return list(
            self.db.execute(
                select(Response).where(
                    and_(
                        Response.tenant_id == self.ctx.tenant_id,
                        Response.workspace_id == self.ctx.workspace_id,
                        Response.run_id.in_(run_ids),
                    )
                )
            )
            .scalars()
            .all()
        )

    def _count_runs(self, start: datetime, end: datetime) -> int:
        return int(
            self.db.execute(
                select(func.count(Run.id)).where(
                    and_(
                        Run.tenant_id == self.ctx.tenant_id,
                        Run.workspace_id == self.ctx.workspace_id,
                        Run.started_at >= start,
                        Run.started_at <= end,
                    )
                )
            ).scalar_one()
            or 0
        )

    @staticmethod
    def _citation_knowledge_id(citation: Any) -> str | None:
        if not isinstance(citation, dict):
            return None
        for key in ("knowledge_id", "knowledge_ref", "source_knowledge_id"):
            value = citation.get(key)
            if isinstance(value, str) and value:
                return value
        metadata = citation.get("metadata")
        if isinstance(metadata, dict):
            value = metadata.get("knowledge_id")
            if isinstance(value, str) and value:
                return value
        return None

    @staticmethod
    def _cost_by_run(costs: list[RunCostEntry]) -> dict[str, float]:
        totals: dict[str, float] = defaultdict(float)
        for cost in costs:
            totals[cost.run_id] += float(cost.amount or 0)
        return totals

    @staticmethod
    def _failure_reason(run: Run) -> str | None:
        return run.error_message or run.error_code

    def _recent_run_payload(
        self,
        run: Run,
        cost_by_run: dict[str, float],
        observe_summaries: dict[str, Any],
    ) -> RecentRunResponse:
        return RecentRunResponse(
            run_id=run.id,
            mode=run.mode,
            kind=run.kind,
            subject_kind=run.subject_kind,
            subject_id=run.subject_id,
            status=run.status,
            cost_usd=round(cost_by_run.get(run.id, 0.0), 6),
            failure_reason=self._failure_reason(run),
            started_at=to_iso8601(run.started_at),
            duration_ms=run.duration_ms,
            observe_summary=observe_summaries.get(run.id),
            detail_url=f"/observe/runs/{run.id}",
        )

    @staticmethod
    def _recent_run_sort_key(run: Run) -> tuple[int, float]:
        status_rank = 0 if run.status == "failed" else 1
        started_at = run.started_at
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=UTC)
        return (status_rank, -started_at.timestamp())

    def _recent_mainline_runs(self, runs: list[Run]) -> list[Run]:
        mainline_runs = [
            run
            for run in runs
            if run.mode in MAINLINE_RUN_MODES or (run.kind in MAINLINE_RUN_MODES if run.kind else False)
        ]
        return sorted(mainline_runs, key=self._recent_run_sort_key)[:10]

    def _latest_row_fields(self, run: Run | None, cost_by_run: dict[str, float]) -> dict[str, Any]:
        if not run:
            return {
                "latest_run_id": None,
                "latest_run_status": None,
                "latest_run_cost_usd": 0.0,
                "latest_failure_reason": None,
                "detail_url": None,
            }
        return {
            "latest_run_id": run.id,
            "latest_run_status": run.status,
            "latest_run_cost_usd": round(cost_by_run.get(run.id, 0.0), 6),
            "latest_failure_reason": self._failure_reason(run),
            "detail_url": f"/observe/runs/{run.id}",
        }

    def _metric_run_fields(self, run: Run | None, cost_by_run: dict[str, float]) -> dict[str, Any]:
        if not run:
            return {}
        return {
            "run_id": run.id,
            "detail_url": f"/observe/runs/{run.id}",
            "status": run.status,
            "cost_usd": round(cost_by_run.get(run.id, 0.0), 6),
            "failure_reason": self._failure_reason(run),
        }

    @staticmethod
    def _latest_run(current: Run | None, candidate: Run | None) -> Run | None:
        if candidate is None:
            return current
        if current is None or candidate.started_at > current.started_at:
            return candidate
        return current

    def _paginate_rows(self, rows: list[dict[str, Any]], *, page_token: str | None, page_size: int) -> tuple[list[dict[str, Any]], DashboardPageResponse]:
        limit, token_obj = parse_page_params(page_token, page_size, max_page_size=50)
        offset = token_obj.offset if token_obj else 0
        page_items = rows[offset : offset + limit]
        next_offset = offset + len(page_items) if offset + len(page_items) < len(rows) else None
        next_token = PageToken(offset=next_offset, limit=limit).to_string() if next_offset is not None else None
        return page_items, DashboardPageResponse(
            page_size=len(page_items),
            next_page_token=next_token,
            total_count=len(rows),
        )

    def _filter_rows(self, rows: list[dict[str, Any]], q: str | None) -> list[dict[str, Any]]:
        if not q:
            return rows
        needle = q.strip().lower()
        if not needle:
            return rows
        return [
            row
            for row in rows
            if needle in str(row.get("id", "")).lower()
            or needle in str(row.get("name", "")).lower()
            or needle in str(row.get("description", "")).lower()
        ]

    def _aggregate(
        self,
        runs: list[Run],
        steps: list[RunStep],
        tool_calls_by_step: dict[str, RunStepToolCall],
        responses: list[Response],
        *,
        window_start: datetime,
        bucket: timedelta,
    ) -> dict[str, Any]:
        run_by_id = {run.id: run for run in runs}
        steps_by_run: dict[str, list[RunStep]] = defaultdict(list)
        for step in steps:
            steps_by_run[step.run_id].append(step)

        agent_summary_map: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "run_count": 0,
                "failed_run_count": 0,
                "duration_sum": 0,
                "duration_count": 0,
                "last_run_at": None,
                "last_error": None,
            }
        )
        workflow_map: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"step_count": 0, "failed_step_count": 0, "latencies": [], "affected_agents": set()}
        )
        tool_health_map: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"call_count": 0, "failed_call_count": 0, "timeout_count": 0, "retry_count": 0, "latencies": [], "error_codes": defaultdict(int), "agents": set()}
        )
        knowledge_map: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "query_count": 0,
                "failed_query_count": 0,
                "result_count": 0,
                "citation_count": 0,
                "score_sum": 0.0,
                "score_count": 0,
                "agents": set(),
            }
        )
        trend: dict[str, dict[str, int]] = defaultdict(
            lambda: {"run_count": 0, "failed_run_count": 0, "tool_count": 0, "tool_failed_count": 0, "retrieval_count": 0, "retrieval_failed_count": 0}
        )

        for run in runs:
            bucket_key = self._bucket_key(run.started_at, window_start, bucket)
            trend[bucket_key]["run_count"] += 1
            if run.status == "failed":
                trend[bucket_key]["failed_run_count"] += 1
            if run.subject_kind == "agent" and run.subject_id:
                summary = agent_summary_map[run.subject_id]
                summary["run_count"] += 1
                if run.status == "failed":
                    summary["failed_run_count"] += 1
                    summary["last_error"] = run.error_message or run.error_code
                if run.duration_ms is not None:
                    summary["duration_sum"] += int(run.duration_ms)
                    summary["duration_count"] += 1
                started_at = to_iso8601(run.started_at)
                if started_at and (summary["last_run_at"] is None or started_at > summary["last_run_at"]):
                    summary["last_run_at"] = started_at

        for step in steps:
            metrics = step.metrics_json if isinstance(step.metrics_json, dict) else {}
            run = run_by_id.get(step.run_id)
            agent_id = run.subject_id if run and run.subject_kind == "agent" else None
            bucket_key = self._bucket_key(step.started_at, window_start, bucket)
            latency = self._int_metric(metrics, "latency_ms")

            if step.node_id:
                workflow = workflow_map[step.node_id]
                workflow["step_count"] += 1
                if step.status == "failed":
                    workflow["failed_step_count"] += 1
                if latency:
                    workflow["latencies"].append(latency)
                if agent_id:
                    workflow["affected_agents"].add(agent_id)

            tool_call = tool_calls_by_step.get(step.id)
            if tool_call is not None:
                tool_ref = tool_call.tool_ref
                trend[bucket_key]["tool_count"] += 1
                tool = tool_health_map[tool_ref]
                tool["call_count"] += 1
                if tool_call.status == "failed":
                    tool["failed_call_count"] += 1
                    trend[bucket_key]["tool_failed_count"] += 1
                    code = tool_call.error_code or step.error_code or "unknown"
                    tool["error_codes"][code] += 1
                    error_message = tool_call.error_message or step.error_message or ""
                    if "timeout" in code.lower() or "timeout" in error_message.lower():
                        tool["timeout_count"] += 1
                tool["retry_count"] += max(0, tool_call.attempt_count - 1)
                if latency:
                    tool["latencies"].append(latency)
                if agent_id:
                    tool["agents"].add(agent_id)

            if step.step_type in {"retrieval", "rerank"}:
                trend[bucket_key]["retrieval_count"] += 1
                knowledge_id = metrics.get("knowledge_id")
                if not isinstance(knowledge_id, str) or not knowledge_id:
                    knowledge_id = "unknown"
                knowledge = knowledge_map[knowledge_id]
                knowledge["query_count"] += 1
                if step.status == "failed":
                    knowledge["failed_query_count"] += 1
                    trend[bucket_key]["retrieval_failed_count"] += 1
                result_count = self._int_metric(metrics, "result_count")
                citation_count = self._int_metric(metrics, "citation_count") or result_count
                knowledge["result_count"] += result_count
                knowledge["citation_count"] += citation_count
                avg_score = self._float_metric(metrics, "avg_score")
                if avg_score is not None and result_count > 0:
                    knowledge["score_sum"] += avg_score * result_count
                    knowledge["score_count"] += result_count
                if agent_id:
                    knowledge["agents"].add(agent_id)
            elif step.status == "failed" and run and run.subject_kind == "knowledge":
                knowledge = knowledge_map[run.subject_id or "unknown"]
                knowledge["query_count"] += 1
                knowledge["failed_query_count"] += 1

        for response in responses:
            run = run_by_id.get(response.run_id or "")
            if not run:
                continue
            citations = (response.output_json or {}).get("citations") if isinstance(response.output_json, dict) else None
            if not isinstance(citations, list):
                continue
            citation_counts: dict[str, int] = defaultdict(int)
            for citation in citations:
                knowledge_id = self._citation_knowledge_id(citation)
                if knowledge_id:
                    citation_counts[knowledge_id] += 1
            for knowledge_id, citation_count in citation_counts.items():
                knowledge = knowledge_map[knowledge_id]
                if int(knowledge["query_count"]) <= 0:
                    knowledge["query_count"] += 1
                knowledge["result_count"] += citation_count
                knowledge["citation_count"] += citation_count
                if run.subject_kind == "agent" and run.subject_id:
                    knowledge["agents"].add(run.subject_id)

        return {
            "agent_summary_map": agent_summary_map,
            "workflow_map": workflow_map,
            "tool_health_map": tool_health_map,
            "knowledge_map": knowledge_map,
            "trend": trend,
            "steps_by_run": steps_by_run,
        }

    def _build_trend_rows(self, trend: dict[str, dict[str, int]], window_start: datetime, window_end: datetime, bucket: timedelta) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        cursor = window_start
        while cursor <= window_end:
            key = to_iso8601(cursor) or ""
            value = trend.get(key, {})
            run_count = int(value.get("run_count", 0))
            failed_run_count = int(value.get("failed_run_count", 0))
            rows.append(
                {
                    "bucket": key,
                    "run_count": run_count,
                    "failed_run_count": failed_run_count,
                    "success_rate": round(1 - self._rate(failed_run_count, run_count), 4) if run_count else 0.0,
                    "tool_count": int(value.get("tool_count", 0)),
                    "tool_failed_count": int(value.get("tool_failed_count", 0)),
                    "retrieval_count": int(value.get("retrieval_count", 0)),
                    "retrieval_failed_count": int(value.get("retrieval_failed_count", 0)),
                }
            )
            cursor += bucket
        return rows

    def _percentile(self, values: list[int], percentile: float) -> int:
        if not values:
            return 0
        ordered = sorted(values)
        index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * percentile)))
        return ordered[index]

    async def build_dashboard(
        self,
        *,
        tab: str = "agent_health",
        range_label: str = "24h",
        bucket_label: str = "10m",
        q: str | None = None,
        workspace_scope: str = "all",
        page_token: str | None = None,
        page_size: int = 10,
    ) -> WorkspaceObserveDashboard:
        active_tab = self._normalize_tab(tab)
        now = utc_now()
        range_delta = self._duration(range_label, RANGE_SECONDS, "1h")
        bucket_delta = self._duration(bucket_label, BUCKET_SECONDS, "10m")
        window_start = now - range_delta
        previous_start = window_start - range_delta

        runs = self._scoped_runs(window_start, now)
        steps = self._scoped_steps(window_start, now)
        tool_calls_by_step = self._tool_calls_by_step(steps)
        costs = self._scoped_costs(window_start, now)
        responses = self._responses_for_runs([run.id for run in runs])
        previous_runs = self._scoped_runs(previous_start, window_start)
        previous_costs = self._scoped_costs(previous_start, window_start)
        approvals = self.approval_repo.list(limit=500, offset=0)

        aggregate = self._aggregate(
            runs,
            steps,
            tool_calls_by_step,
            responses,
            window_start=window_start,
            bucket=bucket_delta,
        )
        agent_summary_map = aggregate["agent_summary_map"]
        workflow_map = aggregate["workflow_map"]
        tool_health_map = aggregate["tool_health_map"]
        knowledge_map = aggregate["knowledge_map"]
        trend_rows = self._build_trend_rows(aggregate["trend"], window_start, now, bucket_delta)
        run_by_id = {run.id: run for run in runs}
        cost_by_run = self._cost_by_run(costs)
        observe_summaries = RunService(self.db, self.ctx).build_observe_summaries([run.id for run in runs])
        latest_agent_run: dict[str, Run] = {}
        latest_node_run: dict[str, Run] = {}
        latest_tool_run: dict[str, Run] = {}
        latest_knowledge_run: dict[str, Run] = {}
        latest_run = max(runs, key=lambda item: item.started_at, default=None)
        latest_failed_run = max((run for run in runs if run.status == "failed"), key=lambda item: item.started_at, default=None)
        latest_active_run = max((run for run in runs if run.status in {"queued", "running", "paused"}), key=lambda item: item.started_at, default=None)

        for run in runs:
            if run.subject_kind == "agent" and run.subject_id:
                latest_agent_run[run.subject_id] = self._latest_run(latest_agent_run.get(run.subject_id), run)  # type: ignore[assignment]

        for step in steps:
            run = run_by_id.get(step.run_id)
            if not run:
                continue
            if step.node_id:
                latest_node_run[step.node_id] = self._latest_run(latest_node_run.get(step.node_id), run)  # type: ignore[assignment]
            tool_call = tool_calls_by_step.get(step.id)
            if tool_call is not None:
                latest_tool_run[tool_call.tool_ref] = self._latest_run(
                    latest_tool_run.get(tool_call.tool_ref),
                    run,
                )  # type: ignore[assignment]
            if step.step_type in {"retrieval", "rerank"}:
                metrics = step.metrics_json if isinstance(step.metrics_json, dict) else {}
                knowledge_id = metrics.get("knowledge_id")
                if not isinstance(knowledge_id, str) or not knowledge_id:
                    knowledge_id = "unknown"
                latest_knowledge_run[knowledge_id] = self._latest_run(latest_knowledge_run.get(knowledge_id), run)  # type: ignore[assignment]
            elif step.status == "failed" and run.subject_kind == "knowledge":
                latest_knowledge_run[run.subject_id or "unknown"] = self._latest_run(latest_knowledge_run.get(run.subject_id or "unknown"), run)  # type: ignore[assignment]

        for response in responses:
            run = run_by_id.get(response.run_id or "")
            if not run:
                continue
            citations = (response.output_json or {}).get("citations") if isinstance(response.output_json, dict) else None
            if not isinstance(citations, list):
                continue
            for citation in citations:
                knowledge_id = self._citation_knowledge_id(citation)
                if knowledge_id:
                    latest_knowledge_run[knowledge_id] = self._latest_run(latest_knowledge_run.get(knowledge_id), run)  # type: ignore[assignment]

        failed_run_count = sum(1 for run in runs if run.status == "failed")
        active_run_count = sum(1 for run in runs if run.status in {"queued", "running", "paused"})
        successful_run_count = sum(1 for run in runs if run.status == "succeeded")
        workspace_success_rate = self._rate(successful_run_count, len(runs)) if runs else 1.0
        workspace_health_score = round(workspace_success_rate * 100, 1)
        sampled_run_count = len({step.run_id for step in steps})
        sampling_rate = self._rate(sampled_run_count, len(runs))
        approvals_summary = ApprovalsSummaryResponse(
            pending=sum(1 for item in approvals if item.status == ApprovalStatus.PENDING.value),
            approved=sum(1 for item in approvals if item.status == ApprovalStatus.APPROVED.value),
            rejected=sum(1 for item in approvals if item.status == ApprovalStatus.REJECTED.value),
        )
        total_cost_usd = sum(float(cost.amount or 0) for cost in costs)
        previous_cost_usd = sum(float(cost.amount or 0) for cost in previous_costs)
        previous_run_count = len(previous_runs)
        previous_failed_run_count = sum(1 for run in previous_runs if run.status == "failed")

        agent_summaries = [
            AgentSummaryResponse(
                agent_id=agent_id,
                run_count=int(summary["run_count"]),
                failed_run_count=int(summary["failed_run_count"]),
                last_run_at=summary["last_run_at"],
            )
            for agent_id, summary in sorted(agent_summary_map.items())
        ]
        workflow_bottlenecks = [
            WorkflowBottleneckResponse(
                node_id=node_id,
                step_count=int(summary["step_count"]),
                failed_step_count=int(summary["failed_step_count"]),
            )
            for node_id, summary in sorted(workflow_map.items())
        ]
        tool_health = [
            ToolHealthResponse(
                tool_ref=tool_ref,
                call_count=int(summary["call_count"]),
                failed_call_count=int(summary["failed_call_count"]),
                failure_rate=self._rate(int(summary["failed_call_count"]), int(summary["call_count"])),
                health_status=self._status_from_failure_rate(int(summary["call_count"]), int(summary["failed_call_count"])),
            )
            for tool_ref, summary in sorted(tool_health_map.items())
        ]
        knowledge_quality = [
            KnowledgeQualityResponse(
                knowledge_id=knowledge_id,
                query_count=int(summary["query_count"]),
                failed_query_count=int(summary["failed_query_count"]),
                result_count=int(summary["result_count"]),
                citation_count=int(summary["citation_count"]),
                avg_score=(
                    float(summary["score_sum"]) / int(summary["score_count"])
                    if int(summary["score_count"]) > 0
                    else None
                ),
                failure_rate=self._rate(int(summary["failed_query_count"]), int(summary["query_count"])),
                avg_results_per_query=self._rate(int(summary["result_count"]), int(summary["query_count"])),
                citation_rate=self._rate(int(summary["citation_count"]), int(summary["result_count"])),
                quality_status=self._status_from_failure_rate(int(summary["query_count"]), int(summary["failed_query_count"])),
            )
            for knowledge_id, summary in sorted(knowledge_map.items())
        ]

        active_alert_count = failed_run_count + sum(1 for item in tool_health if item.health_status == "critical") + sum(
            1 for item in knowledge_quality if item.quality_status == "critical"
        )
        overview = DashboardOverviewResponse(
            workspace_health_score=workspace_health_score,
            workspace_health_status=self._status_from_failure_rate(len(runs), failed_run_count),
            active_alert_count=active_alert_count,
            sampling_rate=sampling_rate,
            sampling_status="full" if sampling_rate >= 1 else ("partial" if sampling_rate > 0 else "no_data"),
            refreshed_at=to_iso8601(now) or now.isoformat(),
        )

        metric_cards = [
            MetricCardResponse(id="run_count", label="Runs", value=str(len(runs)), delta=str(len(runs) - previous_run_count), trend=[row["run_count"] for row in trend_rows], tone="blue", **self._metric_run_fields(latest_run, cost_by_run)),
            MetricCardResponse(id="failed_run_count", label="Failed Runs", value=str(failed_run_count), delta=str(failed_run_count - previous_failed_run_count), trend=[row["failed_run_count"] for row in trend_rows], tone="red", **self._metric_run_fields(latest_failed_run, cost_by_run)),
            MetricCardResponse(id="active_run_count", label="Active Runs", value=str(active_run_count), delta="0", trend=[active_run_count], tone="cyan", **self._metric_run_fields(latest_active_run, cost_by_run)),
            MetricCardResponse(id="pending_approvals", label="Pending Approvals", value=str(approvals_summary.pending), delta="0", trend=[approvals_summary.pending], tone="amber"),
            MetricCardResponse(id="total_cost_usd", label="Cost (USD)", value=f"{total_cost_usd:.2f}", delta=f"{total_cost_usd - previous_cost_usd:.2f}", trend=[float(row.get("run_count", 0)) for row in trend_rows], tone="green", **self._metric_run_fields(latest_run, cost_by_run)),
        ]

        priority_alert = None
        if active_alert_count:
            priority_alert = PriorityAlertResponse(
                title="Workflow queue latency is rising" if workflow_bottlenecks else "Run failures need attention",
                started_at=to_iso8601(min((run.started_at for run in runs if run.status == "failed"), default=now)),
                scope=f"{len(workflow_bottlenecks)} workspaces",
                affected_agents=len(agent_summaries),
                duration_label=f"{max(1, int(range_delta.total_seconds() // 60))} min",
                detail_url=f"/observe/runs/{latest_failed_run.id}" if latest_failed_run else "/observe/runs",
            )

        agent_rows = [
            {
                "id": agent.agent_id,
                "name": agent.agent_id,
                "description": "Agent runtime activity",
                "status": self._status_from_failure_rate(agent.run_count, agent.failed_run_count),
                "run_count": agent.run_count,
                "failed_run_count": agent.failed_run_count,
                "success_rate": round(1 - self._rate(agent.failed_run_count, agent.run_count), 4),
                "avg_latency_ms": (
                    round(agent_summary_map[agent.agent_id]["duration_sum"] / agent_summary_map[agent.agent_id]["duration_count"])
                    if agent_summary_map[agent.agent_id]["duration_count"]
                    else 0
                ),
                "last_error": agent_summary_map[agent.agent_id]["last_error"],
                "owner": "Jude",
                "last_run_at": agent.last_run_at,
                **self._latest_row_fields(latest_agent_run.get(agent.agent_id), cost_by_run),
            }
            for agent in agent_summaries
        ]
        workflow_rows = sorted([
            {
                "id": item.node_id,
                "name": item.node_id,
                "description": "Workflow stage",
                "stage": item.node_id,
                "current_queue": item.step_count,
                "avg_wait_ms": self._percentile(workflow_map[item.node_id]["latencies"], 0.5),
                "failure_rate": self._rate(item.failed_step_count, item.step_count),
                "affected_agents": sorted(workflow_map[item.node_id]["affected_agents"]),
                "owner": "Jude",
                **self._latest_row_fields(latest_node_run.get(item.node_id), cost_by_run),
            }
            for item in workflow_bottlenecks
        ], key=lambda row: (-float(row["failure_rate"]), str(row["id"])))
        tool_rows = [
            {
                "id": item.tool_ref,
                "name": item.tool_ref,
                "description": "Tool call reliability",
                "type": "tool",
                "call_count": item.call_count,
                "success_rate": round(1 - item.failure_rate, 4),
                "avg_latency_ms": self._percentile(tool_health_map[item.tool_ref]["latencies"], 0.5),
                "failure_reason": dict(tool_health_map[item.tool_ref]["error_codes"]),
                "related_agents": sorted(tool_health_map[item.tool_ref]["agents"]),
                "owner": "Jude",
                "status": item.health_status,
                **self._latest_row_fields(latest_tool_run.get(item.tool_ref), cost_by_run),
            }
            for item in tool_health
        ]
        knowledge_rows = [
            {
                "id": item.knowledge_id,
                "name": item.knowledge_id,
                "description": "Knowledge retrieval quality",
                "related_agents": sorted(knowledge_map[item.knowledge_id]["agents"]),
                "hit_rate": round(1 - item.failure_rate, 4),
                "missing_answer_rate": item.failure_rate,
                "expired_chunks": 0,
                "last_updated": None,
                "status": item.quality_status,
                "owner": "Jude",
                **self._latest_row_fields(latest_knowledge_run.get(item.knowledge_id), cost_by_run),
            }
            for item in knowledge_quality
        ]

        section_rows_map = {
            "agent_health": agent_rows,
            "workflow_bottlenecks": workflow_rows,
            "tool_reliability": tool_rows,
            "knowledge_quality": knowledge_rows,
        }
        filtered_rows = self._filter_rows(section_rows_map[active_tab], q)
        paged_rows, page = self._paginate_rows(filtered_rows, page_token=page_token, page_size=page_size)

        section = validate_dashboard_section_response(
            {
                "id": active_tab,
                "summary_cards": self._section_summary(active_tab, agent_rows, workflow_rows, tool_rows, knowledge_rows),
                "charts": self._section_charts(active_tab, trend_rows, workflow_rows, tool_rows, knowledge_rows),
                "rows": paged_rows,
                "page": page,
                "empty_state": EmptyStateResponse(
                    title=f"No {TAB_LABELS[active_tab]} data",
                    description="No observability data for the selected time range.",
                ),
            }
        )

        return WorkspaceObserveDashboard(
            overview=overview,
            metric_cards=metric_cards,
            priority_alert=priority_alert,
            tabs=[
                DashboardTabResponse(id="agent_health", label=TAB_LABELS["agent_health"], count=len(agent_rows)),
                DashboardTabResponse(id="workflow_bottlenecks", label=TAB_LABELS["workflow_bottlenecks"], count=len(workflow_rows)),
                DashboardTabResponse(id="tool_reliability", label=TAB_LABELS["tool_reliability"], count=len(tool_rows)),
                DashboardTabResponse(id="knowledge_quality", label=TAB_LABELS["knowledge_quality"], count=len(knowledge_rows)),
            ],
            section=section,
            recent_runs=[
                self._recent_run_payload(run, cost_by_run, observe_summaries)
                for run in self._recent_mainline_runs(runs)
            ],
        )

    def _section_summary(
        self,
        tab: str,
        agent_rows: list[dict[str, Any]],
        workflow_rows: list[dict[str, Any]],
        tool_rows: list[dict[str, Any]],
        knowledge_rows: list[dict[str, Any]],
    ) -> list[MetricCardResponse]:
        if tab == "agent_health":
            healthy = sum(1 for row in agent_rows if row["status"] == "healthy")
            return [
                MetricCardResponse(id="healthy_agents", label="Healthy Agents", value=str(healthy), tone="green"),
                MetricCardResponse(id="warning_agents", label="Agents Needing Attention", value=str(len(agent_rows) - healthy), tone="red"),
            ]
        if tab == "workflow_bottlenecks":
            return [
                MetricCardResponse(id="bottlenecks", label="Bottlenecks", value=str(len(workflow_rows)), tone="red"),
                MetricCardResponse(id="queued", label="Current Queue", value=str(sum(row["current_queue"] for row in workflow_rows)), tone="amber"),
            ]
        if tab == "tool_reliability":
            avg_success = sum(row["success_rate"] for row in tool_rows) / len(tool_rows) if tool_rows else 0
            return [
                MetricCardResponse(id="avg_success_rate", label="Avg Success Rate", value=self._percent(avg_success), tone="green"),
                MetricCardResponse(id="tool_count", label="Tools", value=str(len(tool_rows)), tone="blue"),
            ]
        avg_hit = sum(row["hit_rate"] for row in knowledge_rows) / len(knowledge_rows) if knowledge_rows else 0
        return [
            MetricCardResponse(id="hit_rate", label="Citation Coverage", value=self._percent(avg_hit), tone="green"),
            MetricCardResponse(id="knowledge_count", label="Knowledge Bases", value=str(len(knowledge_rows)), tone="blue"),
        ]

    def _section_charts(
        self,
        tab: str,
        trend_rows: list[dict[str, Any]],
        workflow_rows: list[dict[str, Any]],
        tool_rows: list[dict[str, Any]],
        knowledge_rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if tab == "agent_health":
            return {
                "trend": trend_rows,
                "health_distribution": [
                    {"status": "healthy", "count": sum(1 for row in trend_rows if row["failed_run_count"] == 0 and row["run_count"] > 0)},
                    {"status": "warning", "count": sum(1 for row in trend_rows if row["failed_run_count"] > 0)},
                ],
                "alert_compression": {"raw_alerts": sum(row["failed_run_count"] for row in trend_rows), "compressed_alerts": 1 if any(row["failed_run_count"] for row in trend_rows) else 0},
            }
        if tab == "workflow_bottlenecks":
            waits = [row["avg_wait_ms"] for row in workflow_rows]
            return {
                "bottleneck_flow": workflow_rows,
                "queue_distribution": workflow_rows,
                "latency_percentiles": {
                    "p50": self._percentile(waits, 0.5),
                    "p95": self._percentile(waits, 0.95),
                    "p99": self._percentile(waits, 0.99),
                },
            }
        if tab == "tool_reliability":
            error_distribution: dict[str, int] = defaultdict(int)
            for row in tool_rows:
                for key, value in row["failure_reason"].items():
                    error_distribution[key] += value
            return {
                "trend": trend_rows,
                "error_distribution": [{"type": key, "count": value} for key, value in sorted(error_distribution.items())],
            }
        return {
            "trend": trend_rows,
            "quality_score": round(sum(row["hit_rate"] for row in knowledge_rows) / len(knowledge_rows) * 100, 1) if knowledge_rows else 100.0,
            "low_quality_sources": sorted(knowledge_rows, key=lambda row: row["hit_rate"])[:5],
        }
