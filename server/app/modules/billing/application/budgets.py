""" budgets

Spending limits per workspace, API key, user or agent, per UTC day or month.

Spend is read from two places so it is current without scanning a month of
usage facts: completed days come from the daily usage aggregates, and today
comes straight from the cost ledger, which every call writes before it
returns. An agent budget reads its whole period from the ledger, joined to the
runs the agent executed, because aggregates are not kept per agent.

A hard-stop budget refuses a call when it is spent. Calls admitted but not yet
finished have no cost recorded, so each admitted call also holds a short
reservation of the period's average call cost; a call is refused when the
reservations already in flight would carry spend past the limit. That keeps
concurrent callers from overshooting a limit by more than about one call.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, Protocol

from sqlalchemy import and_, func, or_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.commons.errors import (
    BudgetExhaustedError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.runs import Run, RunCostEntry
from app.kernel.runtime.db.models.usage import UsageDailyAggregate
from app.modules.billing.application.schemas import BudgetCreate, BudgetUpdate
from app.modules.billing.domain.models import BUDGET_PERIODS, BUDGET_SCOPES, Budget

logger = logging.getLogger(__name__)

ZERO = Decimal("0")


@dataclass(frozen=True)
class BudgetPeriod:
    start: date
    end: date
    """Exclusive."""

    @property
    def starts_at(self) -> datetime:
        return datetime.combine(self.start, time.min, tzinfo=UTC)

    @property
    def resets_at(self) -> datetime:
        return datetime.combine(self.end, time.min, tzinfo=UTC)


def budget_period(period: str, now: datetime) -> BudgetPeriod:
    """The UTC calendar period containing ``now``."""
    today = (now if now.tzinfo else now.replace(tzinfo=UTC)).astimezone(UTC).date()
    if period == "day":
        return BudgetPeriod(today, today + timedelta(days=1))
    start = today.replace(day=1)
    end = (start + timedelta(days=32)).replace(day=1)
    return BudgetPeriod(start, end)


@dataclass(frozen=True)
class BudgetSpend:
    spent: Decimal
    calls: int

    @property
    def average_call(self) -> Decimal:
        return self.spent / self.calls if self.calls else ZERO


def _scope_on_aggregates(budget: Budget) -> list[Any]:
    if budget.scope_kind == "api_key":
        return [UsageDailyAggregate.api_key_id == (budget.scope_id or "")]
    if budget.scope_kind == "user":
        return [UsageDailyAggregate.user_id == (budget.scope_id or "")]
    return []


def _scope_on_runs(budget: Budget) -> list[Any]:
    if budget.scope_kind == "api_key":
        return [Run.api_key_id == budget.scope_id]
    if budget.scope_kind == "user":
        return [Run.user_id == budget.scope_id]
    if budget.scope_kind == "agent":
        return [Run.subject_kind == "agent", Run.subject_id == budget.scope_id]
    return []


async def _ledger_spend(db: AsyncSession, budget: Budget, since: datetime) -> BudgetSpend:
    clauses = [
        RunCostEntry.tenant_id == budget.tenant_id,
        RunCostEntry.workspace_id == budget.workspace_id,
        RunCostEntry.created_at >= since,
        RunCostEntry.currency == budget.currency,
        RunCostEntry.amount.is_not(None),
    ]
    query = select(func.coalesce(func.sum(RunCostEntry.amount), 0), func.count(RunCostEntry.id))
    run_clauses = _scope_on_runs(budget)
    if run_clauses:
        query = query.join(Run, Run.id == RunCostEntry.run_id)
        clauses.extend(run_clauses)
    total, calls = (await db.exec(query.where(and_(*clauses)))).one()
    return BudgetSpend(Decimal(str(total)), int(calls))


async def budget_spend(db: AsyncSession, budget: Budget, now: datetime) -> BudgetSpend:
    """What the budget's scope has spent in its current period, up to now."""
    period = budget_period(budget.period, now)
    if budget.scope_kind == "agent":
        return await _ledger_spend(db, budget, period.starts_at)
    today = budget_period("day", now)
    past = BudgetSpend(ZERO, 0)
    if period.start < today.start:
        total, calls = (
            await db.exec(
                select(
                    func.coalesce(func.sum(UsageDailyAggregate.amount), 0),
                    func.coalesce(func.sum(UsageDailyAggregate.call_count), 0),
                ).where(
                    and_(
                        UsageDailyAggregate.tenant_id == budget.tenant_id,
                        UsageDailyAggregate.workspace_id == budget.workspace_id,
                        UsageDailyAggregate.day >= period.start,
                        UsageDailyAggregate.day < today.start,
                        UsageDailyAggregate.currency == budget.currency,
                        *_scope_on_aggregates(budget),
                    )
                )
            )
        ).one()
        past = BudgetSpend(Decimal(str(total)), int(calls))
    current = await _ledger_spend(db, budget, today.starts_at)
    return BudgetSpend(past.spent + current.spent, past.calls + current.calls)


class BudgetReservations(Protocol):
    """Short-lived holds on a budget for calls admitted but not yet costed."""

    async def in_flight(self, budget_id: str) -> int: ...
    async def reserve(self, budget_id: str) -> None: ...


class BudgetBlockRecorder(Protocol):
    """Writes a refused call into the audit ledger."""

    async def record_block(self, ctx: RequestContext, *, details: dict[str, Any]) -> None: ...


def _spent_message(budget: Budget, spend: BudgetSpend, reason: str) -> str:
    limit = f"{budget.amount.normalize():f} {budget.currency}"
    spent = f"{spend.spent.normalize():f}"
    if reason == "reserved":
        return (
            f"Budget '{budget.name}' has {spent} of {limit} spent this {budget.period} "
            "and the rest is held by calls in flight"
        )
    return f"Budget '{budget.name}' is spent: {spent} of {limit} this {budget.period}"


class BudgetGuard:
    """Refuses calls that a hard-stop budget of their scope cannot pay for."""

    def __init__(
        self,
        db: AsyncSession,
        ctx: RequestContext,
        *,
        reservations: BudgetReservations | None = None,
        recorder: BudgetBlockRecorder | None = None,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.db = db
        self.ctx = ctx
        self.reservations = reservations
        self.recorder = recorder
        self.clock = clock

    async def _agent_of(self, run_id: str | None) -> str | None:
        if not run_id:
            return None
        run = await self.db.get(Run, run_id)
        if run is not None and run.subject_kind == "agent":
            return run.subject_id
        return None

    async def applicable(self, run_id: str | None) -> list[Budget]:
        scopes = [Budget.scope_kind == "workspace"]
        scopes.append(and_(Budget.scope_kind == "user", Budget.scope_id == self.ctx.user_id))
        if self.ctx.api_key_id:
            scopes.append(and_(Budget.scope_kind == "api_key", Budget.scope_id == self.ctx.api_key_id))
        agent_id = await self._agent_of(run_id)
        if agent_id:
            scopes.append(and_(Budget.scope_kind == "agent", Budget.scope_id == agent_id))
        query = select(Budget).where(
            and_(
                Budget.tenant_id == self.ctx.tenant_id,
                Budget.workspace_id == self.ctx.workspace_id,
                Budget.status == "active",
                Budget.hard_stop.is_(True),
                or_(*scopes),
            )
        )
        return list((await self.db.exec(query)).scalars())

    async def _refuse(
        self, budget: Budget, spend: BudgetSpend, *, operation: str, reason: str, now: datetime
    ) -> None:
        period = budget_period(budget.period, now)
        details = {
            "reason": reason,
            "budget_id": budget.id,
            "budget_name": budget.name,
            "scope_kind": budget.scope_kind,
            "scope_id": budget.scope_id,
            "period": budget.period,
            "amount": format(budget.amount, "f"),
            "spent": format(spend.spent, "f"),
            "currency": budget.currency,
            "resets_at": period.resets_at.isoformat(),
            "operation": operation,
        }
        if self.recorder is not None:
            try:
                await self.recorder.record_block(self.ctx, details=details)
            except Exception:
                logger.warning("Could not audit a budget refusal", exc_info=True)
        raise BudgetExhaustedError(_spent_message(budget, spend, reason), details)

    async def check(self, *, operation: str, run_id: str | None = None) -> None:
        budgets = await self.applicable(run_id)
        if not budgets:
            return
        now = self.clock()
        for budget in budgets:
            spend = await budget_spend(self.db, budget, now)
            if spend.spent >= budget.amount:
                await self._refuse(budget, spend, operation=operation, reason="spent", now=now)
            estimate = spend.average_call
            if estimate > 0 and self.reservations is not None:
                in_flight = await self.reservations.in_flight(budget.id)
                if spend.spent + estimate * (in_flight + 1) > budget.amount:
                    await self._refuse(budget, spend, operation=operation, reason="reserved", now=now)
        if self.reservations is not None:
            for budget in budgets:
                await self.reservations.reserve(budget.id)


class CompositeCreditGuard:
    """Runs several guards in order; the first refusal wins."""

    def __init__(self, *guards: Any) -> None:
        self.guards = [guard for guard in guards if guard is not None]

    async def check(self, *, operation: str, run_id: str | None = None) -> None:
        for guard in self.guards:
            await guard.check(operation=operation, run_id=run_id)


def _validated(scope_kind: str, scope_id: str | None, period: str) -> None:
    if scope_kind not in BUDGET_SCOPES:
        raise ValidationError(f"Unknown budget scope: {scope_kind}", {"param": "scope_kind"})
    if scope_kind == "workspace" and scope_id:
        raise ValidationError("A workspace budget takes no scope_id", {"param": "scope_id"})
    if scope_kind != "workspace" and not scope_id:
        raise ValidationError(f"A {scope_kind} budget needs a scope_id", {"param": "scope_id"})
    if period not in BUDGET_PERIODS:
        raise ValidationError(f"Unknown budget period: {period}", {"param": "period"})


@dataclass(frozen=True)
class BudgetStatus:
    budget: Budget
    period: BudgetPeriod
    spent: Decimal
    remaining: Decimal
    percent: Decimal
    forecast: Decimal
    """Spend projected to the end of the period at the rate so far."""


class BudgetService:
    """Create, change and report on a workspace's budgets."""

    def __init__(
        self,
        db: AsyncSession,
        ctx: RequestContext,
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.db = db
        self.ctx = ctx
        self.clock = clock

    def _require_governor(self) -> None:
        if not self.ctx.can_govern():
            raise ForbiddenError("Workspace owner or admin role required to manage budgets")

    async def _get(self, budget_id: str) -> Budget:
        budget = await self.db.get(Budget, budget_id)
        if (
            budget is None
            or budget.tenant_id != self.ctx.tenant_id
            or budget.workspace_id != self.ctx.workspace_id
        ):
            raise NotFoundError(f"Budget not found: {budget_id}")
        return budget

    async def list_budgets(self) -> list[Budget]:
        query = (
            select(Budget)
            .where(
                and_(
                    Budget.tenant_id == self.ctx.tenant_id,
                    Budget.workspace_id == self.ctx.workspace_id,
                )
            )
            .order_by(Budget.name)
        )
        return list((await self.db.exec(query)).scalars())

    async def get_budget(self, budget_id: str) -> Budget:
        return await self._get(budget_id)

    async def create_budget(self, data: BudgetCreate) -> Budget:
        self._require_governor()
        _validated(data.scope_kind, data.scope_id, data.period)
        budget = Budget(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            name=data.name,
            scope_kind=data.scope_kind,
            scope_id=data.scope_id,
            period=data.period,
            amount=data.amount,
            currency=data.currency,
            thresholds_json=data.thresholds,
            hard_stop=data.hard_stop,
            created_by=self.ctx.user_id,
        )
        self.db.add(budget)
        await self.db.commit()
        return budget

    async def update_budget(self, budget_id: str, data: BudgetUpdate) -> Budget:
        self._require_governor()
        budget = await self._get(budget_id)
        changes = data.model_dump(exclude_unset=True)
        for field in ("name", "amount", "hard_stop", "status"):
            if changes.get(field) is not None:
                setattr(budget, field, changes[field])
        if changes.get("thresholds") is not None:
            budget.thresholds_json = changes["thresholds"]
        budget.updated_at = utc_now()
        await self.db.commit()
        return budget

    async def delete_budget(self, budget_id: str) -> None:
        self._require_governor()
        budget = await self._get(budget_id)
        await self.db.delete(budget)
        await self.db.commit()

    async def status(self, budget_id: str) -> BudgetStatus:
        budget = await self._get(budget_id)
        now = self.clock()
        period = budget_period(budget.period, now)
        spend = await budget_spend(self.db, budget, now)
        elapsed = max((now - period.starts_at).total_seconds(), 1.0)
        length = (period.resets_at - period.starts_at).total_seconds()
        forecast = (spend.spent * Decimal(str(length / elapsed))).quantize(Decimal("0.000001"))
        return BudgetStatus(
            budget=budget,
            period=period,
            spent=spend.spent,
            remaining=max(budget.amount - spend.spent, ZERO),
            percent=(spend.spent / budget.amount * 100).quantize(Decimal("0.01"))
            if budget.amount
            else ZERO,
            forecast=forecast,
        )
