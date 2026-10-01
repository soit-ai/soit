"""Filtered reads over the cost ledger, for checking it against a provider's bill.

Every cost entry is one metered call. These queries filter entries by the
run's API key, principal and source and by the entry's model, provider, tool,
currency and pricing status, list them, and summarize them per currency with
the unpriced and estimated entries counted apart. Amounts in different
currencies are never added together.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, case, func, literal, select

from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.runs import Run, RunCostEntry
from app.kernel.runtime.runs.protocols import RunQueryRepositoryProtocol
from app.kernel.runtime.runs.schemas import (
    COST_PRICING_STATUSES,
    CostGroupBy,
    CostPricingStatus,
    CostReconciliationGroupResponse,
    CostReconciliationResponse,
    CostUnpricedReasonResponse,
    RunCostEntryResponse,
)

MAX_GROUPS = 500
"""Most rows one grouped summary answers; ``groups_truncated`` says when more exist."""


@dataclass(frozen=True)
class CostEntryFilter:
    """What a cost read narrows to. Unset fields do not filter."""

    since: datetime | None = None
    until: datetime | None = None
    until_inclusive: bool = True
    run_id: str | None = None
    api_key_id: str | None = None
    user_id: str | None = None
    source: str | None = None
    model_ref: str | None = None
    provider_slug: str | None = None
    tool_ref: str | None = None
    source_port: str | None = None
    operation: str | None = None
    currency: str | None = None
    pricing_status: CostPricingStatus | None = None
    upstream_id: str | None = None
    upstream_request_id: str | None = None


def _estimated_expr() -> Any:
    return func.coalesce(RunCostEntry.pricing_snapshot_json["usage_estimated"].as_boolean(), False)


def _status_expr() -> Any:
    """SQL twin of ``cost_pricing_status``."""
    return case(
        (RunCostEntry.amount.is_(None), literal("unpriced")),
        (_estimated_expr(), literal("estimated")),
        (RunCostEntry.amount == 0, literal("free")),
        else_=literal("priced"),
    )


def _group_expr(group_by: CostGroupBy) -> Any:
    if group_by == "model":
        return RunCostEntry.model_ref
    if group_by == "provider":
        return RunCostEntry.provider_slug
    if group_by == "tool":
        return RunCostEntry.tool_ref
    if group_by == "api_key":
        return Run.api_key_id
    if group_by == "user":
        return Run.user_id
    if group_by == "source":
        return Run.source
    if group_by == "operation":
        return RunCostEntry.operation
    return func.date(RunCostEntry.created_at)


class CostLedgerQueries:
    """Workspace-scoped reads of ``run_cost_entries`` joined to their runs."""

    def __init__(self, db: RunQueryRepositoryProtocol, ctx: RequestContext):
        self.db = db
        self.ctx = ctx

    def _clauses(self, filters: CostEntryFilter) -> list[Any]:
        clauses: list[Any] = [
            RunCostEntry.tenant_id == self.ctx.tenant_id,
            RunCostEntry.workspace_id == self.ctx.workspace_id,
        ]
        if filters.since:
            clauses.append(RunCostEntry.created_at >= filters.since)
        if filters.until:
            if filters.until_inclusive:
                clauses.append(RunCostEntry.created_at <= filters.until)
            else:
                clauses.append(RunCostEntry.created_at < filters.until)
        equal_to = (
            (RunCostEntry.run_id, filters.run_id),
            (Run.api_key_id, filters.api_key_id),
            (Run.user_id, filters.user_id),
            (Run.source, filters.source),
            (RunCostEntry.model_ref, filters.model_ref),
            (RunCostEntry.provider_slug, filters.provider_slug),
            (RunCostEntry.tool_ref, filters.tool_ref),
            (RunCostEntry.source_port, filters.source_port),
            (RunCostEntry.operation, filters.operation),
            (RunCostEntry.currency, filters.currency),
            (RunCostEntry.upstream_id, filters.upstream_id),
            (RunCostEntry.upstream_request_id, filters.upstream_request_id),
        )
        clauses.extend(column == value for column, value in equal_to if value)
        if filters.pricing_status:
            clauses.append(_status_expr() == filters.pricing_status)
        return clauses

    def _join(self, query: Any) -> Any:
        return query.outerjoin(
            Run,
            and_(
                Run.id == RunCostEntry.run_id,
                Run.tenant_id == RunCostEntry.tenant_id,
                Run.workspace_id == RunCostEntry.workspace_id,
            ),
        )

    async def list_entries(
        self,
        filters: CostEntryFilter,
        *,
        limit: int,
        offset: int,
    ) -> list[RunCostEntryResponse]:
        """Entries oldest first, each with its run's key, principal and source."""
        query = self._join(
            select(RunCostEntry, Run.api_key_id, Run.user_id, Run.source).select_from(RunCostEntry)
        )
        query = (
            query.where(and_(*self._clauses(filters)))
            .order_by(RunCostEntry.created_at, RunCostEntry.id)
            .offset(offset)
            .limit(limit)
        )
        entries: list[RunCostEntryResponse] = []
        for entry, api_key_id, user_id, run_source in (await self.db.exec(query)).all():
            response = RunCostEntryResponse.model_validate(entry)
            entries.append(
                response.model_copy(
                    update={"api_key_id": api_key_id, "user_id": user_id, "run_source": run_source}
                )
            )
        return entries

    async def reconcile(
        self,
        filters: CostEntryFilter,
        *,
        group_by: CostGroupBy | None = None,
    ) -> CostReconciliationResponse:
        """Totals per currency, entries per pricing status, and why entries went unpriced."""
        clauses = self._clauses(filters)
        status = _status_expr()

        status_counts = dict.fromkeys(COST_PRICING_STATUSES, 0)
        query = self._join(select(status, func.count()).select_from(RunCostEntry))
        for name, count in (await self.db.exec(query.where(and_(*clauses)).group_by(status))).all():
            status_counts[str(name)] = int(count or 0)

        amounts: dict[str, Decimal] = {}
        estimated_amounts: dict[str, Decimal] = {}
        query = self._join(
            select(
                RunCostEntry.currency,
                func.sum(RunCostEntry.amount),
                func.sum(case((_estimated_expr(), RunCostEntry.amount), else_=literal(0))),
            ).select_from(RunCostEntry)
        )
        query = query.where(and_(*clauses, RunCostEntry.amount.is_not(None))).group_by(RunCostEntry.currency)
        for currency, total, estimated in (await self.db.exec(query)).all():
            if not currency:
                continue
            amounts[str(currency)] = Decimal(str(total or 0))
            if estimated:
                estimated_amounts[str(currency)] = Decimal(str(estimated))

        reason = func.coalesce(RunCostEntry.pricing_snapshot_json["reason"].as_string(), literal("unknown"))
        query = self._join(select(reason, func.count()).select_from(RunCostEntry))
        query = query.where(and_(*clauses, RunCostEntry.amount.is_(None))).group_by(reason)
        unpriced_reasons = sorted(
            (
                CostUnpricedReasonResponse(reason=str(name), entry_count=int(count or 0))
                for name, count in (await self.db.exec(query)).all()
            ),
            key=lambda item: (-item.entry_count, item.reason),
        )

        groups: list[CostReconciliationGroupResponse] = []
        truncated = False
        if group_by:
            groups, truncated = await self._groups(clauses, group_by)

        return CostReconciliationResponse(
            since=filters.since,
            until=filters.until,
            entry_count=sum(status_counts.values()),
            status_counts=status_counts,
            amounts=amounts,
            estimated_amounts=estimated_amounts,
            unpriced_reasons=unpriced_reasons,
            group_by=group_by,
            groups=groups,
            groups_truncated=truncated,
        )

    async def _groups(
        self,
        clauses: list[Any],
        group_by: CostGroupBy,
    ) -> tuple[list[CostReconciliationGroupResponse], bool]:
        key = _group_expr(group_by)
        query = self._join(
            select(
                key,
                RunCostEntry.currency,
                func.count(),
                func.sum(RunCostEntry.amount),
                func.sum(case((_estimated_expr(), literal(1)), else_=literal(0))),
                func.sum(case((RunCostEntry.amount.is_(None), literal(1)), else_=literal(0))),
                func.sum(func.coalesce(RunCostEntry.total_tokens, 0)),
            ).select_from(RunCostEntry)
        )
        query = (
            query.where(and_(*clauses))
            .group_by(key, RunCostEntry.currency)
            .order_by(key, RunCostEntry.currency)
            .limit(MAX_GROUPS + 1)
        )
        rows = list((await self.db.exec(query)).all())
        groups = [
            CostReconciliationGroupResponse(
                key=None if value is None else str(value),
                currency=currency,
                entry_count=int(count or 0),
                amount=None if total is None else Decimal(str(total)),
                estimated_count=int(estimated or 0),
                unpriced_count=int(unpriced or 0),
                total_tokens=int(tokens or 0),
            )
            for value, currency, count, total, estimated, unpriced, tokens in rows[:MAX_GROUPS]
        ]
        return groups, len(rows) > MAX_GROUPS
