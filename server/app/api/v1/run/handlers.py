""" handlers

Run request handlers (thin orchestration).
"""

import csv
import io
from datetime import datetime

from app.infra.db.pagination import PaginatedResponse, parse_page_params
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.runs.schemas import (
    RunAuditLogResponse,
    RunCostByModelResponse,
    RunCostByModeResponse,
    RunCostByProviderResponse,
    RunCostBySubjectResponse,
    RunCostDailyResponse,
    RunCostEntryResponse,
    RunCostSummaryResponse,
    RunDetailResponse,
    RunResponse,
    RunStepMetricsSummaryResponse,
    RunStepResponse,
)
from app.kernel.runtime.runs.service import RunService


class RunHandlers:
    """Handlers for run API endpoints."""

    def __init__(self, service: RunService):
        self.service = service

    async def list_runs(
        self,
        ctx: RequestContext,
        *,
        mode: str | None = None,
        kind: str | None = None,
        subject_kind: str | None = None,
        subject_id: str | None = None,
        subject_version_id: str | None = None,
        subject_version_ids: list[str] | None = None,
        status: str | None = None,
        trace_id: str | None = None,
        user_id: str | None = None,
        started_after: datetime | None = None,
        started_before: datetime | None = None,
        include_observe_summary: bool = False,
        has_tool_call: bool | None = None,
        has_citation: bool | None = None,
        has_audit: bool | None = None,
        page_token: str | None = None,
        page_size: int = 20,
        with_total: bool = False,
    ) -> PaginatedResponse[RunResponse]:
        """List runs with pagination and optional filters."""
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        limit_plus = limit + 1

        runs = self.service.list_runs(
            mode=mode,
            kind=kind,
            subject_version_id=subject_version_id,
            subject_version_ids=subject_version_ids,
            subject_kind=subject_kind,
            subject_id=subject_id,
            status=status,
            trace_id=trace_id,
            user_id=user_id,
            started_after=started_after,
            started_before=started_before,
            include_observe_summary=include_observe_summary,
            has_tool_call=has_tool_call,
            has_citation=has_citation,
            has_audit=has_audit,
            limit=limit_plus,
            offset=offset,
        )

        has_next = len(runs) > limit
        items = runs[:limit]
        next_offset = offset + len(items) if has_next else None
        total = (
            self.service.count_runs(
                mode=mode,
                kind=kind,
                subject_version_id=subject_version_id,
                subject_version_ids=subject_version_ids,
                subject_kind=subject_kind,
                subject_id=subject_id,
                status=status,
                trace_id=trace_id,
                user_id=user_id,
                started_after=started_after,
                started_before=started_before,
                has_tool_call=has_tool_call,
                has_citation=has_citation,
                has_audit=has_audit,
            )
            if with_total
            else None
        )

        return PaginatedResponse.create(
            items=items,
            page_size=len(items),
            has_next=has_next,
            next_offset=next_offset,
            total=total,
        )

    async def get_run(
        self,
        ctx: RequestContext,
        run_id: str,
        *,
        include_steps: bool = True,
        include_artifacts: bool = True,
        include_cost: bool = True,
    ) -> RunDetailResponse:
        """Get run detail."""
        return self.service.get_run(
            run_id,
            include_steps=include_steps,
            include_artifacts=include_artifacts,
            include_cost=include_cost,
        )

    async def list_steps(
        self,
        ctx: RequestContext,
        *,
        run_id: str | None = None,
        trace_id: str | None = None,
        step_id: str | None = None,
        step_type: str | None = None,
        status: str | None = None,
        node_id: str | None = None,
        started_after: datetime | None = None,
        started_before: datetime | None = None,
        ended_after: datetime | None = None,
        ended_before: datetime | None = None,
        page_token: str | None = None,
        page_size: int = 20,
        with_total: bool = False,
    ) -> PaginatedResponse[RunStepResponse]:
        """List run steps with pagination and optional filters."""
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        limit_plus = limit + 1

        steps = self.service.list_steps(
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
            limit=limit_plus,
            offset=offset,
        )

        has_next = len(steps) > limit
        items = steps[:limit]
        next_offset = offset + len(items) if has_next else None
        total = (
            self.service.count_steps(
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
            if with_total
            else None
        )

        return PaginatedResponse.create(
            items=items,
            page_size=len(items),
            has_next=has_next,
            next_offset=next_offset,
            total=total,
        )

    async def summarize_step_metrics(
        self,
        ctx: RequestContext,
        *,
        run_id: str | None = None,
        trace_id: str | None = None,
        step_id: str | None = None,
        step_type: str | None = None,
        status: str | None = None,
        node_id: str | None = None,
        started_after: datetime | None = None,
        started_before: datetime | None = None,
        ended_after: datetime | None = None,
        ended_before: datetime | None = None,
    ) -> list[RunStepMetricsSummaryResponse]:
        """Summarize run step metrics by type/status."""
        return self.service.summarize_step_metrics(
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

    async def summarize_costs(
        self,
        ctx: RequestContext,
        *,
        mode: str | None = None,
        kind: str | None = None,
        subject_version_id: str | None = None,
        subject_version_ids: list[str] | None = None,
        subject_kind: str | None = None,
        subject_id: str | None = None,
        status: str | None = None,
        started_after: datetime | None = None,
        started_before: datetime | None = None,
    ) -> RunCostSummaryResponse:
        """Summarize run costs."""
        return self.service.summarize_costs(
            mode=mode,
            kind=kind,
            subject_version_id=subject_version_id,
            subject_version_ids=subject_version_ids,
            subject_kind=subject_kind,
            subject_id=subject_id,
            status=status,
            started_after=started_after,
            started_before=started_before,
        )

    async def list_cost_entries(
        self,
        ctx: RequestContext,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        run_id: str | None = None,
        page_token: str | None = None,
        page_size: int = 200,
    ) -> PaginatedResponse[RunCostEntryResponse]:
        """List cost entries with pagination for incremental billing sync."""
        limit, token_obj = parse_page_params(page_token, page_size, max_page_size=500)
        offset = token_obj.offset if token_obj else 0
        limit_plus = limit + 1

        entries = self.service.list_cost_entries(
            since=since,
            until=until,
            run_id=run_id,
            limit=limit_plus,
            offset=offset,
        )

        has_next = len(entries) > limit
        items = entries[:limit]
        next_offset = offset + len(items) if has_next else None

        return PaginatedResponse.create(
            items=items,
            page_size=len(items),
            has_next=has_next,
            next_offset=next_offset,
        )

    async def summarize_costs_by_day(
        self,
        ctx: RequestContext,
        *,
        mode: str | None = None,
        kind: str | None = None,
        subject_version_id: str | None = None,
        subject_version_ids: list[str] | None = None,
        subject_kind: str | None = None,
        subject_id: str | None = None,
        status: str | None = None,
        started_after: datetime | None = None,
        started_before: datetime | None = None,
    ) -> list[RunCostDailyResponse]:
        """Summarize run costs by day."""
        return self.service.summarize_costs_by_day(
            mode=mode,
            kind=kind,
            subject_version_id=subject_version_id,
            subject_version_ids=subject_version_ids,
            subject_kind=subject_kind,
            subject_id=subject_id,
            status=status,
            started_after=started_after,
            started_before=started_before,
        )

    async def summarize_costs_by_subject(
        self,
        ctx: RequestContext,
        *,
        mode: str | None = None,
        kind: str | None = None,
        subject_version_ids: list[str] | None = None,
        subject_kind: str | None = None,
        subject_id: str | None = None,
        subject_version_id: str | None = None,
        status: str | None = None,
        started_after: datetime | None = None,
        started_before: datetime | None = None,
    ) -> list[RunCostBySubjectResponse]:
        """Summarize run costs by subject version."""
        return self.service.summarize_costs_by_subject(
            mode=mode,
            kind=kind,
            subject_version_ids=subject_version_ids,
            subject_kind=subject_kind,
            subject_id=subject_id,
            subject_version_id=subject_version_id,
            status=status,
            started_after=started_after,
            started_before=started_before,
        )

    async def summarize_costs_by_mode(
        self,
        ctx: RequestContext,
        *,
        mode: str | None = None,
        subject_version_id: str | None = None,
        subject_version_ids: list[str] | None = None,
        subject_kind: str | None = None,
        subject_id: str | None = None,
        status: str | None = None,
        started_after: datetime | None = None,
        started_before: datetime | None = None,
        kind: str | None = None,
    ) -> list[RunCostByModeResponse]:
        """Summarize run costs by mode."""
        return self.service.summarize_costs_by_mode(
            mode=mode,
            subject_version_id=subject_version_id,
            subject_version_ids=subject_version_ids,
            subject_kind=subject_kind,
            subject_id=subject_id,
            status=status,
            started_after=started_after,
            started_before=started_before,
            kind=kind,
        )

    async def summarize_costs_by_provider(
        self,
        ctx: RequestContext,
        *,
        mode: str | None = None,
        kind: str | None = None,
        subject_version_id: str | None = None,
        subject_version_ids: list[str] | None = None,
        subject_kind: str | None = None,
        subject_id: str | None = None,
        status: str | None = None,
        started_after: datetime | None = None,
        started_before: datetime | None = None,
    ) -> list[RunCostByProviderResponse]:
        """Summarize run costs by provider."""
        return self.service.summarize_costs_by_provider(
            mode=mode,
            kind=kind,
            subject_version_id=subject_version_id,
            subject_version_ids=subject_version_ids,
            subject_kind=subject_kind,
            subject_id=subject_id,
            status=status,
            started_after=started_after,
            started_before=started_before,
        )

    async def summarize_costs_by_model(
        self,
        ctx: RequestContext,
        *,
        mode: str | None = None,
        kind: str | None = None,
        subject_version_id: str | None = None,
        subject_version_ids: list[str] | None = None,
        subject_kind: str | None = None,
        subject_id: str | None = None,
        status: str | None = None,
        started_after: datetime | None = None,
        started_before: datetime | None = None,
    ) -> list[RunCostByModelResponse]:
        """Summarize run costs by model."""
        return self.service.summarize_costs_by_model(
            mode=mode,
            kind=kind,
            subject_version_id=subject_version_id,
            subject_version_ids=subject_version_ids,
            subject_kind=subject_kind,
            subject_id=subject_id,
            status=status,
            started_after=started_after,
            started_before=started_before,
        )

    async def export_runs_csv(
        self,
        ctx: RequestContext,
        *,
        mode: str | None = None,
        kind: str | None = None,
        subject_version_id: str | None = None,
        subject_version_ids: list[str] | None = None,
        subject_kind: str | None = None,
        subject_id: str | None = None,
        status: str | None = None,
        trace_id: str | None = None,
        user_id: str | None = None,
        started_after: datetime | None = None,
        started_before: datetime | None = None,
        limit: int = 1000,
    ) -> str:
        """Export runs to CSV."""
        runs = self.service.list_runs(
            mode=mode,
            kind=kind,
            subject_version_id=subject_version_id,
            subject_version_ids=subject_version_ids,
            subject_kind=subject_kind,
            subject_id=subject_id,
            status=status,
            trace_id=trace_id,
            user_id=user_id,
            started_after=started_after,
            started_before=started_before,
            limit=limit,
            offset=0,
        )
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "run_id",
                "mode",
                "kind",
                "status",
                "subject_version_id",
                "user_id",
                "started_at",
                "ended_at",
                "duration_ms",
                "error_code",
                "error_message",
            ]
        )
        for run in runs:
            writer.writerow(
                [
                    run.id,
                    run.mode,
                    run.kind,
                    run.status,
                    run.subject_version_id,
                    run.user_id,
                    run.started_at.isoformat() if run.started_at else "",
                    run.ended_at.isoformat() if run.ended_at else "",
                    run.duration_ms or "",
                    run.error_code or "",
                    run.error_message or "",
                ]
            )
        return output.getvalue()

    async def list_audits(
        self,
        ctx: RequestContext,
        *,
        run_id: str | None = None,
        step_id: str | None = None,
        step_type: str | None = None,
        gateway_type: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        page_token: str | None = None,
        page_size: int = 50,
        with_total: bool = False,
    ) -> PaginatedResponse[RunAuditLogResponse]:
        """List audit logs for a run."""
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        limit_plus = limit + 1

        entries = self.service.list_audits(
            run_id=run_id,
            step_id=step_id,
            step_type=step_type,
            gateway_type=gateway_type,
            since=since,
            until=until,
            limit=limit_plus,
            offset=offset,
        )

        has_next = len(entries) > limit
        items = entries[:limit]
        next_offset = offset + len(items) if has_next else None
        total = (
            self.service.count_audits(
                run_id=run_id,
                step_id=step_id,
                step_type=step_type,
                gateway_type=gateway_type,
                since=since,
                until=until,
            )
            if with_total
            else None
        )

        return PaginatedResponse.create(
            items=items,
            page_size=len(items),
            has_next=has_next,
            next_offset=next_offset,
            total=total,
        )
