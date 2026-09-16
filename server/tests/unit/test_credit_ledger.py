"""Credit ledger: deduction consumer idempotency, conversion, and service math."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.commons.errors import CreditExhaustedError
from app.kernel.runtime.db.models.events import EventOutbox
from app.modules.billing.application.guard import CreditBalanceGuard
from app.modules.billing.application.service import CreditService
from app.modules.billing.domain.models import CreditLedgerEntry
from app.modules.billing.events import CREDIT_BALANCE_LOW
from app.modules.billing.handlers.on_cost_recorded import handle_cost_recorded_credit
from app.modules.identity.domain.models import WorkspaceMembership
from app.modules.notification.domain.models import Notification
from app.modules.notification.handlers.on_credit_balance_low import (
    handle_credit_balance_low,
)
from app.settings.settings import settings

pytestmark = pytest.mark.asyncio


def _cost_event(
    event_id: str,
    *,
    cost_entry_id: str = "cost_entry_1",
    amount: str | None = "0.25",
    currency: str | None = "USD",
) -> EventOutbox:
    return EventOutbox(
        event_id=event_id,
        event_type="cost.recorded",
        tenant_id="tenant-credit",
        workspace_id="workspace-credit",
        idempotency_key=event_id,
        payload_json={
            "cost_entry_id": cost_entry_id,
            "tenant_id": "tenant-credit",
            "workspace_id": "workspace-credit",
            "run_id": "run_credit",
            "billing_basis": "tokens",
            "billed_quantity": "10",
            "prompt_tokens": 6,
            "completion_tokens": 4,
            # The writer stringifies amount, so unpriced rows arrive as "None".
            "amount": str(amount),
            "currency": currency,
        },
    )


async def _ledger_rows(db: AsyncSession) -> list[CreditLedgerEntry]:
    rows = list((await db.exec(select(CreditLedgerEntry))).all())
    return [row if hasattr(row, "id") else row[0] for row in rows]


async def test_priced_event_books_one_negative_deduction(async_db: AsyncSession) -> None:
    row = _cost_event("evt_cost_credit_1")
    async_db.add(row)
    await async_db.flush()

    await handle_cost_recorded_credit(async_db, row)

    entries = await _ledger_rows(async_db)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.kind == "deduction"
    assert entry.cost_entry_id == "cost_entry_1"
    assert entry.credits_delta == Decimal("-250.000000")
    assert entry.amount == Decimal("0.25")
    assert entry.currency == "USD"
    assert entry.conversion_snapshot_json["rate"] == "1000"
    assert entry.conversion_snapshot_json["source_event_id"] == "evt_cost_credit_1"
    assert entry.created_by == "system:credit-deduction"


async def test_duplicate_event_id_books_nothing(async_db: AsyncSession) -> None:
    row = _cost_event("evt_cost_credit_dup")
    async_db.add(row)
    await async_db.flush()

    await handle_cost_recorded_credit(async_db, row)
    await handle_cost_recorded_credit(async_db, row)

    assert len(await _ledger_rows(async_db)) == 1


async def test_same_cost_entry_under_new_event_id_is_not_double_booked(
    async_db: AsyncSession,
) -> None:
    first = _cost_event("evt_cost_credit_a", cost_entry_id="cost_entry_same")
    second = _cost_event("evt_cost_credit_b", cost_entry_id="cost_entry_same")
    async_db.add(first)
    async_db.add(second)
    await async_db.flush()

    await handle_cost_recorded_credit(async_db, first)
    await handle_cost_recorded_credit(async_db, second)

    assert len(await _ledger_rows(async_db)) == 1


async def test_unpriced_event_books_nothing(async_db: AsyncSession) -> None:
    unpriced = _cost_event("evt_cost_credit_unpriced", amount=None, currency=None)
    async_db.add(unpriced)
    await async_db.flush()

    await handle_cost_recorded_credit(async_db, unpriced)

    assert await _ledger_rows(async_db) == []


async def test_unknown_currency_books_zero_credit_adjustment(async_db: AsyncSession) -> None:
    unsupported = _cost_event(
        "evt_cost_credit_eur", cost_entry_id="cost_entry_eur", currency="EUR"
    )
    async_db.add(unsupported)
    await async_db.flush()

    await handle_cost_recorded_credit(async_db, unsupported)

    entries = await _ledger_rows(async_db)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.kind == "adjustment"
    assert entry.credits_delta == Decimal("0")
    assert entry.cost_entry_id == "cost_entry_eur"
    assert entry.currency == "EUR"
    assert entry.amount == Decimal("0.25")
    assert entry.conversion_snapshot_json["reason"] == "no_rate_configured_for_currency"

    # Replaying under a fresh event id must not double-book the adjustment.
    replay = _cost_event(
        "evt_cost_credit_eur_replay", cost_entry_id="cost_entry_eur", currency="EUR"
    )
    async_db.add(replay)
    await async_db.flush()
    await handle_cost_recorded_credit(async_db, replay)
    assert len(await _ledger_rows(async_db)) == 1


async def test_balance_is_signed_sum_of_grants_and_deductions(
    async_db: AsyncSession, ctx
) -> None:
    service = CreditService(async_db, ctx)
    await service.grant(credits=Decimal("1000"), note="initial top-up")

    row = _cost_event("evt_cost_credit_balance", cost_entry_id="cost_entry_balance")
    row.tenant_id = ctx.tenant_id
    row.workspace_id = ctx.workspace_id
    row.payload_json = {
        **row.payload_json,
        "tenant_id": ctx.tenant_id,
        "workspace_id": ctx.workspace_id,
    }
    async_db.add(row)
    await async_db.flush()
    await handle_cost_recorded_credit(async_db, row)

    balance = await service.get_balance()
    assert balance.balance == Decimal("750.000000")
    assert balance.granted_total == Decimal("1000")
    assert balance.deducted_total == Decimal("-250.000000")
    assert balance.entry_count == 2

    entries = await service.list_entries()
    assert len(entries) == 2
    deductions = await service.list_entries(kind="deduction")
    assert len(deductions) == 1
    assert deductions[0].run_id == "run_credit"


async def test_grant_rejects_non_positive_credits(async_db: AsyncSession, ctx) -> None:
    service = CreditService(async_db, ctx)
    with pytest.raises(ValueError, match="positive"):
        await service.grant(credits=Decimal("0"))


async def test_guard_is_noop_when_enforcement_disabled(async_db: AsyncSession, ctx) -> None:
    guard = CreditBalanceGuard(async_db, ctx)
    await guard.check(operation="chat")  # zero balance, but enforcement is off


async def test_guard_hard_stops_exhausted_balance(
    async_db: AsyncSession, ctx, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "credit_enforcement_enabled", True)
    guard = CreditBalanceGuard(async_db, ctx)

    with pytest.raises(CreditExhaustedError) as excinfo:
        await guard.check(operation="chat")
    assert excinfo.value.details["operation"] == "chat"

    await CreditService(async_db, ctx).grant(credits=Decimal("500"), note="top-up")
    await guard.check(operation="chat")  # positive balance passes


async def test_guard_warns_below_threshold(
    async_db: AsyncSession, ctx, monkeypatch, caplog
) -> None:
    monkeypatch.setattr(settings, "credit_enforcement_enabled", True)
    monkeypatch.setattr(settings, "credit_low_balance_threshold", 100.0)
    await CreditService(async_db, ctx).grant(credits=Decimal("50"), note="small top-up")
    guard = CreditBalanceGuard(async_db, ctx)

    with caplog.at_level("WARNING"):
        await guard.check(operation="chat")
    assert any("credit balance low" in record.message for record in caplog.records)


async def _balance_alert_events(db: AsyncSession) -> list[EventOutbox]:
    rows = list(
        (
            await db.exec(select(EventOutbox).where(EventOutbox.event_type == CREDIT_BALANCE_LOW))
        ).all()
    )
    return [row if hasattr(row, "event_id") else row[0] for row in rows]


async def _grant(db: AsyncSession, ctx, credits: str) -> None:
    await CreditService(db, ctx).grant(credits=Decimal(credits))


async def _deduct(db: AsyncSession, ctx, event_id: str, cost_entry_id: str) -> None:
    row = _cost_event(event_id, cost_entry_id=cost_entry_id)
    row.tenant_id = ctx.tenant_id
    row.workspace_id = ctx.workspace_id
    row.payload_json = {
        **row.payload_json,
        "tenant_id": ctx.tenant_id,
        "workspace_id": ctx.workspace_id,
    }
    db.add(row)
    await db.flush()
    await handle_cost_recorded_credit(db, row)


async def test_low_threshold_crossing_publishes_one_alert(async_db: AsyncSession, ctx) -> None:
    await _grant(async_db, ctx, "300")  # deduction of 250 lands at 50, below the 100 default
    await _deduct(async_db, ctx, "evt_cross_low", "cost_entry_cross_low")

    events = await _balance_alert_events(async_db)
    assert len(events) == 1
    payload = events[0].payload_json
    assert payload["state"] == "low"
    assert payload["balance"] == "50.000000"

    # A further deduction that stays below the threshold does not re-alert
    # (until the balance is exhausted, which is a separate crossing).
    await _deduct(async_db, ctx, "evt_cross_low_again", "cost_entry_cross_low_again")
    events = await _balance_alert_events(async_db)
    assert {event.payload_json["state"] for event in events} == {"low", "exhausted"}


async def test_exhaustion_crossing_publishes_error_alert(async_db: AsyncSession, ctx) -> None:
    await _grant(async_db, ctx, "200")  # deduction of 250 lands at -50
    await _deduct(async_db, ctx, "evt_cross_exhausted", "cost_entry_cross_exhausted")

    events = await _balance_alert_events(async_db)
    assert len(events) == 1
    assert events[0].payload_json["state"] == "exhausted"

    # Already exhausted: further deductions do not spam alerts.
    await _deduct(async_db, ctx, "evt_cross_exhausted_2", "cost_entry_cross_exhausted_2")
    assert len(await _balance_alert_events(async_db)) == 1


async def test_healthy_deduction_publishes_no_alert(async_db: AsyncSession, ctx) -> None:
    await _grant(async_db, ctx, "1000")
    await _deduct(async_db, ctx, "evt_no_cross", "cost_entry_no_cross")
    assert await _balance_alert_events(async_db) == []


async def test_balance_alert_notifies_owner_and_admin_only(async_db: AsyncSession, ctx) -> None:
    for user_id, role in (
        ("user_owner", "Owner"),
        ("user_admin", "Admin"),
        ("user_viewer", "Viewer"),
    ):
        async_db.add(
            WorkspaceMembership(
                tenant_id=ctx.tenant_id,
                workspace_id=ctx.workspace_id,
                user_id=user_id,
                role=role,
            )
        )
    event = EventOutbox(
        event_id="evt_credit_low_notify",
        event_type=CREDIT_BALANCE_LOW,
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        idempotency_key="evt_credit_low_notify",
        payload_json={
            "state": "low",
            "tenant_id": ctx.tenant_id,
            "workspace_id": ctx.workspace_id,
            "balance": "50.000000",
            "threshold": "100",
            "ledger_entry_id": "ledger_1",
        },
    )
    async_db.add(event)
    await async_db.flush()

    await handle_credit_balance_low(async_db, event)
    await handle_credit_balance_low(async_db, event)  # idempotent replay

    rows = list((await async_db.exec(select(Notification))).all())
    notifications = [row if hasattr(row, "id") else row[0] for row in rows]
    assert {n.user_id for n in notifications} == {"user_owner", "user_admin"}
    assert all(n.type == "alert" for n in notifications)
    assert all(n.severity == "warning" for n in notifications)
    assert all(n.source_module == "billing" for n in notifications)
    assert all(n.meta["state"] == "low" for n in notifications)


async def test_balance_status_reflects_enforcement_thresholds(
    async_db: AsyncSession, ctx, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "credit_enforcement_enabled", True)
    monkeypatch.setattr(settings, "credit_low_balance_threshold", 100.0)
    service = CreditService(async_db, ctx)

    assert (await service.get_balance()).status == "exhausted"
    await service.grant(credits=Decimal("50"))
    assert (await service.get_balance()).status == "low"
    await service.grant(credits=Decimal("500"))
    balance = await service.get_balance()
    assert balance.status == "ok"
    assert balance.enforcement_enabled is True
    assert balance.low_balance_threshold == Decimal("100")
