"""End to end: a priced record_cost books exactly one credit deduction."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlmodel import Session, select

from app.kernel.events.dispatcher import OutboxDispatcher
from app.kernel.runtime.runs.writer import TraceWriter
from app.modules.billing.application.service import CreditService
from app.modules.billing.domain.models import CreditLedgerEntry
from app.modules.identity.domain.models import WorkspaceMembership
from app.modules.notification.domain.models import Notification
from app.wiring.outbox_handlers import get_outbox_registry, register_outbox_handlers


@pytest.mark.asyncio
async def test_priced_usage_row_is_deducted_once_through_dispatcher(db: Session, ctx) -> None:
    register_outbox_handlers()
    reg = get_outbox_registry()

    writer = TraceWriter(db, ctx, event_bus=None)
    run = writer.create_run("agent")
    priced = writer.record_cost(
        run_id=run.id,
        step_id=None,
        billing_basis="tokens",
        billed_quantity=30,
        currency="USD",
        amount=Decimal("0.5"),
        model_ref="model:test:m",
        source_port="llm",
        operation="chat",
        prompt_tokens=20,
        completion_tokens=10,
        total_tokens=30,
        latency_ms=100,
    )
    unpriced = writer.record_cost(
        run_id=run.id,
        step_id=None,
        billing_basis="requests",
        billed_quantity=1,
        source_port="tools",
        operation="invoke",
        request_count=1,
    )

    dispatcher = OutboxDispatcher(db, reg)
    assert await dispatcher.run_once(batch_limit=50) >= 1
    db.commit()

    rows = list(db.exec(select(CreditLedgerEntry)).all())
    entries = [row if hasattr(row, "id") else row[0] for row in rows]
    assert len(entries) == 1
    entry = entries[0]
    assert entry.cost_entry_id == priced.id
    assert entry.run_id == run.id
    assert entry.credits_delta == Decimal("-500.000000")
    assert entry.cost_entry_id != unpriced.id

    # Replaying the dispatcher must not double-book.
    await dispatcher.run_once(batch_limit=50)
    db.commit()
    rows = list(db.exec(select(CreditLedgerEntry)).all())
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_exhaustion_crossing_lands_in_admin_inbox(db: Session, ctx) -> None:
    register_outbox_handlers()
    reg = get_outbox_registry()

    db.add(
        WorkspaceMembership(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            user_id=ctx.user_id,
            role="Owner",
        )
    )
    CreditService(db, ctx).grant(credits=Decimal("100"), note="small top-up")
    db.commit()

    writer = TraceWriter(db, ctx, event_bus=None)
    run = writer.create_run("agent")
    writer.record_cost(
        run_id=run.id,
        step_id=None,
        billing_basis="tokens",
        billed_quantity=30,
        currency="USD",
        amount=Decimal("0.5"),  # 500 credits at the default rate
        model_ref="model:test:m",
        source_port="llm",
        operation="chat",
        prompt_tokens=20,
        completion_tokens=10,
        total_tokens=30,
    )

    dispatcher = OutboxDispatcher(db, reg)
    # First pass books the deduction and publishes the balance alert;
    # second pass fans the alert out to the inbox.
    await dispatcher.run_once(batch_limit=50)
    db.commit()
    await dispatcher.run_once(batch_limit=50)
    db.commit()

    rows = list(db.exec(select(Notification)).all())
    notifications = [row if hasattr(row, "id") else row[0] for row in rows]
    assert len(notifications) == 1
    notification = notifications[0]
    assert notification.user_id == ctx.user_id
    assert notification.severity == "error"
    assert notification.source_module == "billing"
    assert notification.meta["state"] == "exhausted"
