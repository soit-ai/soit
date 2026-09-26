"""Budget threshold alerts for COST_RECORDED outbox events.

After each priced usage fact, every active budget whose scope covers it is
measured; a threshold the fact carried spend across raises one
BUDGET_THRESHOLD_REACHED event. The event id is derived from the budget, the
period and the threshold, and outbox event ids are unique, so concurrent
consumers that both see the crossing publish it once.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.commons.time import utc_now
from app.kernel.events.checkpoint import try_claim_consumer_slot
from app.kernel.events.envelope import DomainEventEnvelope
from app.kernel.events.outbox_repo import OutboxRepository
from app.kernel.events.publisher import OutboxPublisher
from app.kernel.runtime.db.models.events import EventOutbox
from app.kernel.runtime.db.models.runs import Run, RunCostEntry
from app.modules.billing.application.budgets import budget_period, budget_spend
from app.modules.billing.domain.models import Budget
from app.modules.billing.events import BUDGET_THRESHOLD_REACHED

logger = logging.getLogger(__name__)

CONSUMER_NAME = "billing.budget.thresholds"


async def _budgets_covering(db: AsyncSession, entry: RunCostEntry, run: Run | None) -> list[Budget]:
    scopes = [Budget.scope_kind == "workspace"]
    if run is not None and run.user_id:
        scopes.append(and_(Budget.scope_kind == "user", Budget.scope_id == run.user_id))
    if run is not None and run.api_key_id:
        scopes.append(and_(Budget.scope_kind == "api_key", Budget.scope_id == run.api_key_id))
    if run is not None and run.subject_kind == "agent" and run.subject_id:
        scopes.append(and_(Budget.scope_kind == "agent", Budget.scope_id == run.subject_id))
    query = select(Budget).where(
        and_(
            Budget.tenant_id == entry.tenant_id,
            Budget.workspace_id == entry.workspace_id,
            Budget.status == "active",
            Budget.currency == entry.currency,
            or_(*scopes),
        )
    )
    return list((await db.exec(query)).scalars())


async def handle_cost_recorded_budget(db: AsyncSession, row: EventOutbox) -> None:
    """Publish the budget thresholds this usage fact crossed, each once."""
    if not await try_claim_consumer_slot(
        db, consumer_name=CONSUMER_NAME, event_id=row.event_id, result="budget_thresholds"
    ):
        return
    entry_id = (row.payload_json or {}).get("cost_entry_id")
    entry = await db.get(RunCostEntry, str(entry_id)) if entry_id else None
    if entry is None or entry.amount is None or entry.amount <= 0 or not entry.currency:
        return
    run = await db.get(Run, entry.run_id)
    for budget in await _budgets_covering(db, entry, run):
        spend = await budget_spend(db, budget, entry.created_at)
        after = spend.spent / budget.amount * 100
        before = (spend.spent - entry.amount) / budget.amount * 100
        period = budget_period(budget.period, entry.created_at)
        for threshold in budget.thresholds_json or []:
            if not (before < Decimal(threshold) <= after):
                continue
            envelope = DomainEventEnvelope(
                event_id=f"evt_budget_{budget.id}_{period.start.isoformat()}_{threshold}",
                event_type=BUDGET_THRESHOLD_REACHED,
                tenant_id=budget.tenant_id,
                workspace_id=budget.workspace_id,
                subject_type="budget",
                subject_id=budget.id,
                run_id=entry.run_id,
                producer=CONSUMER_NAME,
                occurred_at=utc_now(),
                payload={
                    "budget_id": budget.id,
                    "budget_name": budget.name,
                    "scope_kind": budget.scope_kind,
                    "scope_id": budget.scope_id,
                    "period": budget.period,
                    "period_start": period.start.isoformat(),
                    "threshold": threshold,
                    "percent": format(after.quantize(Decimal("0.01")), "f"),
                    "spent": format(spend.spent, "f"),
                    "amount": format(budget.amount, "f"),
                    "currency": budget.currency,
                    "hard_stop": budget.hard_stop,
                },
            )
            try:
                async with db.begin_nested():
                    OutboxPublisher(OutboxRepository(db)).publish(envelope)
                    await db.flush()
            except IntegrityError:
                logger.debug("Budget threshold already announced: %s", envelope.event_id)
