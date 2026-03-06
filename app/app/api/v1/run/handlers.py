""" handlers

Run request handlers (thin orchestration).
"""

from typing import Optional
import csv
import io
from datetime import datetime

from app.kernel.contracts.context import RequestContext
from app.kernel.trace.service import RunService
from app.kernel.trace.schemas import (
    RunResponse,
    RunDetailResponse,
    RunCostSummaryResponse,
    RunCostDailyResponse,
    RunCostByAppResponse,
    RunCostByModeResponse,
    RunCostByProviderResponse,
    RunCostByModelResponse,
    RunStepResponse,
    RunStepMetricsSummaryResponse,
    RunAuditLogResponse,
)
from app.infra.db.pagination import PaginatedResponse, parse_page_params


class RunHandlers:
    """Handlers for run API endpoints."""

    def __init__(self, service: RunService):
        self.service = service

    @staticmethod
    def _resolve_app_id(app_id: Optional[str], workflow_id: Optional[str]) -> Optional[str]:
        """Resolve app_id from workflow_id alias."""
        return app_id or workflow_id

    async def list_runs(
        self,
        ctx: RequestContext,
        *,
        mode: Optional[str] = None,
        kind: Optional[str] = None,
        app_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        app_version_id: Optional[str] = None,
        app_version_ids: Optional[list[str]] = None,
        status: Optional[str] = None,
        trace_id: Optional[str] = None,
        user_id: Optional[str] = None,
        started_after: Optional[datetime] = None,
        started_before: Optional[datetime] = None,
        page_token: Optional[str] = None,
        page_size: int = 20,
    ) -> PaginatedResponse[RunResponse]:
        """List runs with pagination and optional filters."""
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        limit_plus = limit + 1

        resolved_app_id = self._resolve_app_id(app_id, workflow_id)
        runs = self.service.list_runs(
            mode=mode,
            kind=kind,
            app_id=resolved_app_id,
            app_version_id=app_version_id,
            app_version_ids=app_version_ids,
            status=status,
            trace_id=trace_id,
            user_id=user_id,
            started_after=started_after,
            started_before=started_before,
            limit=limit_plus,
            offset=offset,
        )

        has_next = len(runs) > limit
        items = runs[:limit]
        next_offset = offset + len(items) if has_next else None

        return PaginatedResponse.create(
            items=items,
            page_size=len(items),
            has_next=has_next,
            next_offset=next_offset,
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
        page_token: Optional[str] = None,
        page_size: int = 20,
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

        return PaginatedResponse.create(
            items=items,
            page_size=len(items),
            has_next=has_next,
            next_offset=next_offset,
        )

    async def summarize_step_metrics(
        self,
        ctx: RequestContext,
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
        mode: Optional[str] = None,
        kind: Optional[str] = None,
        app_id: Optional[str] = None,
        app_version_id: Optional[str] = None,
        app_version_ids: Optional[list[str]] = None,
        status: Optional[str] = None,
        started_after: Optional[datetime] = None,
        started_before: Optional[datetime] = None,
    ) -> RunCostSummaryResponse:
        """Summarize run costs."""
        return self.service.summarize_costs(
            mode=mode,
            kind=kind,
            app_id=app_id,
            app_version_id=app_version_id,
            app_version_ids=app_version_ids,
            status=status,
            started_after=started_after,
            started_before=started_before,
        )

    async def summarize_costs_by_day(
        self,
        ctx: RequestContext,
        *,
        mode: Optional[str] = None,
        kind: Optional[str] = None,
        app_id: Optional[str] = None,
        app_version_id: Optional[str] = None,
        app_version_ids: Optional[list[str]] = None,
        status: Optional[str] = None,
        started_after: Optional[datetime] = None,
        started_before: Optional[datetime] = None,
    ) -> list[RunCostDailyResponse]:
        """Summarize run costs by day."""
        return self.service.summarize_costs_by_day(
            mode=mode,
            kind=kind,
            app_id=app_id,
            app_version_id=app_version_id,
            app_version_ids=app_version_ids,
            status=status,
            started_after=started_after,
            started_before=started_before,
        )

    async def summarize_costs_by_app(
        self,
        ctx: RequestContext,
        *,
        mode: Optional[str] = None,
        kind: Optional[str] = None,
        app_id: Optional[str] = None,
        app_version_ids: Optional[list[str]] = None,
        status: Optional[str] = None,
        started_after: Optional[datetime] = None,
        started_before: Optional[datetime] = None,
    ) -> list[RunCostByAppResponse]:
        """Summarize run costs by app version."""
        return self.service.summarize_costs_by_app(
            mode=mode,
            kind=kind,
            app_id=app_id,
            app_version_ids=app_version_ids,
            status=status,
            started_after=started_after,
            started_before=started_before,
        )

    async def summarize_costs_by_mode(
        self,
        ctx: RequestContext,
        *,
        mode: Optional[str] = None,
        app_id: Optional[str] = None,
        app_version_id: Optional[str] = None,
        app_version_ids: Optional[list[str]] = None,
        status: Optional[str] = None,
        started_after: Optional[datetime] = None,
        started_before: Optional[datetime] = None,
        kind: Optional[str] = None,
    ) -> list[RunCostByModeResponse]:
        """Summarize run costs by mode."""
        return self.service.summarize_costs_by_mode(
            mode=mode,
            app_id=app_id,
            app_version_id=app_version_id,
            app_version_ids=app_version_ids,
            status=status,
            started_after=started_after,
            started_before=started_before,
            kind=kind,
        )

    async def summarize_costs_by_provider(
        self,
        ctx: RequestContext,
        *,
        mode: Optional[str] = None,
        kind: Optional[str] = None,
        app_id: Optional[str] = None,
        app_version_id: Optional[str] = None,
        app_version_ids: Optional[list[str]] = None,
        status: Optional[str] = None,
        started_after: Optional[datetime] = None,
        started_before: Optional[datetime] = None,
    ) -> list[RunCostByProviderResponse]:
        """Summarize run costs by provider."""
        return self.service.summarize_costs_by_provider(
            mode=mode,
            kind=kind,
            app_id=app_id,
            app_version_id=app_version_id,
            app_version_ids=app_version_ids,
            status=status,
            started_after=started_after,
            started_before=started_before,
        )

    async def summarize_costs_by_model(
        self,
        ctx: RequestContext,
        *,
        mode: Optional[str] = None,
        kind: Optional[str] = None,
        app_id: Optional[str] = None,
        app_version_id: Optional[str] = None,
        app_version_ids: Optional[list[str]] = None,
        status: Optional[str] = None,
        started_after: Optional[datetime] = None,
        started_before: Optional[datetime] = None,
    ) -> list[RunCostByModelResponse]:
        """Summarize run costs by model."""
        return self.service.summarize_costs_by_model(
            mode=mode,
            kind=kind,
            app_id=app_id,
            app_version_id=app_version_id,
            app_version_ids=app_version_ids,
            status=status,
            started_after=started_after,
            started_before=started_before,
        )

    async def export_runs_csv(
        self,
        ctx: RequestContext,
        *,
        mode: Optional[str] = None,
        kind: Optional[str] = None,
        app_id: Optional[str] = None,
        app_version_id: Optional[str] = None,
        app_version_ids: Optional[list[str]] = None,
        status: Optional[str] = None,
        trace_id: Optional[str] = None,
        user_id: Optional[str] = None,
        started_after: Optional[datetime] = None,
        started_before: Optional[datetime] = None,
        limit: int = 1000,
    ) -> str:
        """Export runs to CSV."""
        runs = self.service.list_runs(
            mode=mode,
            kind=kind,
            app_id=app_id,
            app_version_id=app_version_id,
            app_version_ids=app_version_ids,
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
                "app_version_id",
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
                    run.app_version_id,
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
        run_id: str,
        step_id: Optional[str] = None,
        page_token: Optional[str] = None,
        page_size: int = 50,
    ) -> PaginatedResponse[RunAuditLogResponse]:
        """List audit logs for a run."""
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        limit_plus = limit + 1

        entries = self.service.list_audits(
            run_id=run_id,
            step_id=step_id,
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
