"""Run-level limits a workflow version declares in ``spec.limits``.

The compiler copies the declared limits into ``plan_data["limits"]``; this
module enforces them while the DAG executes. Each check runs before a node is
started, and the wall-clock limit also bounds the wait for nodes already in
flight, so one slow node cannot outlive the run's time budget.

Exceeding a limit stops the run with a ``WorkflowLimitExceeded`` whose
``reason`` matches the agent loop's finish reasons (``time_budget_exceeded``,
``cost_budget_exceeded``, ``tool_budget_exceeded``) plus ``max_steps``, and
the engine records that reason as the run's error code.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.commons.errors import ValidationError
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.runs import RunCostEntry, RunStepToolCall

TIME_BUDGET_EXCEEDED = "time_budget_exceeded"
MAX_STEPS = "max_steps"
COST_BUDGET_EXCEEDED = "cost_budget_exceeded"
TOOL_BUDGET_EXCEEDED = "tool_budget_exceeded"


class WorkflowLimitExceeded(ValidationError):
    """A declared run limit stopped the workflow."""

    def __init__(self, reason: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, {"reason": reason, **(details or {})})
        self.reason = reason


def _positive_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _budget(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except ArithmeticError:
        return None
    return number if number >= 0 else None


@dataclass(frozen=True)
class WorkflowRunLimits:
    """Normalised view of ``plan_data["limits"]``."""

    timeout_ms: int | None = None
    max_steps: int | None = None
    budget: Decimal | None = None
    budget_currency: str = "USD"
    max_tool_calls: int | None = None

    @classmethod
    def from_plan_data(cls, plan_data: dict[str, Any]) -> WorkflowRunLimits:
        raw = plan_data.get("limits") or {}
        if not isinstance(raw, dict):
            return cls()
        timeout_ms = _positive_int(raw.get("timeout_ms"))
        max_steps = _positive_int(raw.get("max_steps"))
        return cls(
            timeout_ms=timeout_ms if timeout_ms else None,
            max_steps=max_steps if max_steps else None,
            budget=_budget(raw.get("budget")),
            budget_currency=str(raw.get("budget_currency") or "USD"),
            max_tool_calls=_positive_int(raw.get("max_tool_calls")),
        )

    @property
    def any(self) -> bool:
        return any(
            value is not None
            for value in (self.timeout_ms, self.max_steps, self.budget, self.max_tool_calls)
        )


class WorkflowLimitGuard:
    """Tracks one execution attempt against its declared limits.

    The wall clock starts when the attempt starts: a run resumed after an
    approval gets a fresh time budget, while steps already completed before
    the pause still count toward ``max_steps``.
    """

    def __init__(
        self,
        limits: WorkflowRunLimits,
        *,
        run_id: str,
        ctx: RequestContext | None,
        completed_steps: int = 0,
    ) -> None:
        self.limits = limits
        self.run_id = run_id
        self.ctx = ctx
        self.steps_started = completed_steps
        self._started_at = time.monotonic()

    def remaining_seconds(self) -> float | None:
        if self.limits.timeout_ms is None:
            return None
        elapsed = time.monotonic() - self._started_at
        return max(0.0, self.limits.timeout_ms / 1000 - elapsed)

    def check_time(self) -> None:
        remaining = self.remaining_seconds()
        if remaining is not None and remaining <= 0:
            raise WorkflowLimitExceeded(
                TIME_BUDGET_EXCEEDED,
                f"Workflow exceeded its time limit of {self.limits.timeout_ms} ms",
                {"timeout_ms": self.limits.timeout_ms},
            )

    async def check_before_node(self, db: AsyncSession, node_id: str) -> None:
        """Raise when starting ``node_id`` would break a declared limit."""

        self.check_time()
        if self.limits.max_steps is not None and self.steps_started >= self.limits.max_steps:
            raise WorkflowLimitExceeded(
                MAX_STEPS,
                f"Workflow reached its limit of {self.limits.max_steps} steps before {node_id}",
                {"max_steps": self.limits.max_steps, "node_id": node_id},
            )
        if self.limits.budget is not None:
            spent = await self._cost_total(db)
            if spent >= self.limits.budget:
                raise WorkflowLimitExceeded(
                    COST_BUDGET_EXCEEDED,
                    f"Workflow spent {spent} {self.limits.budget_currency}, "
                    f"its budget is {self.limits.budget}",
                    {
                        "budget": format(self.limits.budget, "f"),
                        "spent": format(spent, "f"),
                        "currency": self.limits.budget_currency,
                        "node_id": node_id,
                    },
                )
        if self.limits.max_tool_calls is not None:
            calls = await self._tool_call_count(db)
            if calls >= self.limits.max_tool_calls:
                raise WorkflowLimitExceeded(
                    TOOL_BUDGET_EXCEEDED,
                    f"Workflow made {calls} tool calls, its limit is {self.limits.max_tool_calls}",
                    {
                        "max_tool_calls": self.limits.max_tool_calls,
                        "tool_calls": calls,
                        "node_id": node_id,
                    },
                )

    def note_step_started(self) -> None:
        self.steps_started += 1

    def _scope(self, model: type[RunCostEntry] | type[RunStepToolCall]) -> list[Any]:
        clauses: list[Any] = [model.run_id == self.run_id]
        if self.ctx is not None:
            clauses.append(model.tenant_id == self.ctx.tenant_id)
            clauses.append(model.workspace_id == self.ctx.workspace_id)
        return clauses

    async def _cost_total(self, db: AsyncSession) -> Decimal:
        query = select(func.coalesce(func.sum(RunCostEntry.amount), 0)).where(
            *self._scope(RunCostEntry),
            RunCostEntry.currency == self.limits.budget_currency,
        )
        row = (await db.exec(query)).one()  # type: ignore[call-overload]
        value = row if isinstance(row, int | float | Decimal) else row[0]
        return Decimal(str(value))

    async def _tool_call_count(self, db: AsyncSession) -> int:
        query = select(func.count()).select_from(RunStepToolCall).where(
            *self._scope(RunStepToolCall)
        )
        row = (await db.exec(query)).one()  # type: ignore[call-overload]
        value = row if isinstance(row, int) else row[0]
        return int(value)
