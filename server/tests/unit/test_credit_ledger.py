"""Credit ledger: deduction consumer idempotency, conversion, and service math."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlmodel import Session, select

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


def _ledger_rows(db: Session) -> list[CreditLedgerEntry]:
    rows = list(db.exec(select(CreditLedgerEntry)).all())
    return [row if hasattr(row, "id") else row[0] for row in rows]


def test_priced_event_books_one_negative_deduction(db: Session) -> None:
    row = _cost_event("evt_cost_credit_1")
    db.add(row)
    db.flush()

    handle_cost_recorded_credit(db, row)

    entries = _ledger_rows(db)
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


def test_duplicate_event_id_books_nothing(db: Session) -> None:
    row = _cost_event("evt_cost_credit_dup")
    db.add(row)
    db.flush()

    handle_cost_recorded_credit(db, row)
    handle_cost_recorded_credit(db, row)

    assert len(_ledger_rows(db)) == 1


def test_same_cost_entry_under_new_event_id_is_not_double_booked(db: Session) -> None:
    first = _cost_event("evt_cost_credit_a", cost_entry_id="cost_entry_same")
    second = _cost_event("evt_cost_credit_b", cost_entry_id="cost_entry_same")
    db.add(first)
    db.add(second)
    db.flush()

    handle_cost_recorded_credit(db, first)
    handle_cost_recorded_credit(db, second)

    assert len(_ledger_rows(db)) == 1


def test_unpriced_event_books_nothing(db: Session) -> None:
    unpriced = _cost_event("evt_cost_credit_unpriced", amount=None, currency=None)
    db.add(unpriced)
    db.flush()

    handle_cost_recorded_credit(db, unpriced)

    assert _ledger_rows(db) == []


def test_unknown_currency_books_zero_credit_adjustment(db: Session) -> None:
    unsupported = _cost_event(
        "evt_cost_credit_eur", cost_entry_id="cost_entry_eur", currency="EUR"
    )
    db.add(unsupported)
    db.flush()

    handle_cost_recorded_credit(db, unsupported)

    entries = _ledger_rows(db)
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
    db.add(replay)
    db.flush()
    handle_cost_recorded_credit(db, replay)
    assert len(_ledger_rows(db)) == 1


def test_balance_is_signed_sum_of_grants_and_deductions(db: Session, ctx) -> None:
    service = CreditService(db, ctx)
    service.grant(credits=Decimal("1000"), note="initial top-up")

    row = _cost_event("evt_cost_credit_balance", cost_entry_id="cost_entry_balance")
    row.tenant_id = ctx.tenant_id
    row.workspace_id = ctx.workspace_id
    row.payload_json = {
        **row.payload_json,
        "tenant_id": ctx.tenant_id,
        "workspace_id": ctx.workspace_id,
    }
    db.add(row)
    db.flush()
    handle_cost_recorded_credit(db, row)

    balance = service.get_balance()
    assert balance.balance == Decimal("750.000000")
    assert balance.granted_total == Decimal("1000")
    assert balance.deducted_total == Decimal("-250.000000")
    assert balance.entry_count == 2

    entries = service.list_entries()
    assert len(entries) == 2
    deductions = service.list_entries(kind="deduction")
    assert len(deductions) == 1
    assert deductions[0].run_id == "run_credit"


def test_grant_rejects_non_positive_credits(db: Session, ctx) -> None:
    service = CreditService(db, ctx)
    with pytest.raises(ValueError, match="positive"):
        service.grant(credits=Decimal("0"))


@pytest.mark.asyncio
async def test_guard_is_noop_when_enforcement_disabled(db: Session, ctx) -> None:
    guard = CreditBalanceGuard(db, ctx)
    await guard.check(operation="chat")  # zero balance, but enforcement is off


@pytest.mark.asyncio
async def test_guard_hard_stops_exhausted_balance(db: Session, ctx, monkeypatch) -> None:
    monkeypatch.setattr(settings, "credit_enforcement_enabled", True)
    guard = CreditBalanceGuard(db, ctx)

    with pytest.raises(CreditExhaustedError) as excinfo:
        await guard.check(operation="chat")
    assert excinfo.value.details["operation"] == "chat"

    CreditService(db, ctx).grant(credits=Decimal("500"), note="top-up")
    await guard.check(operation="chat")  # positive balance passes


@pytest.mark.asyncio
async def test_guard_warns_below_threshold(db: Session, ctx, monkeypatch, caplog) -> None:
    monkeypatch.setattr(settings, "credit_enforcement_enabled", True)
    monkeypatch.setattr(settings, "credit_low_balance_threshold", 100.0)
    CreditService(db, ctx).grant(credits=Decimal("50"), note="small top-up")
    guard = CreditBalanceGuard(db, ctx)

    with caplog.at_level("WARNING"):
        await guard.check(operation="chat")
    assert any("credit balance low" in record.message for record in caplog.records)


def _balance_alert_events(db: Session) -> list[EventOutbox]:
    rows = list(
        db.exec(
            select(EventOutbox).where(EventOutbox.event_type == CREDIT_BALANCE_LOW)
        ).all()
    )
    return [row if hasattr(row, "event_id") else row[0] for row in rows]


def _grant(db: Session, ctx, credits: str) -> None:
    CreditService(db, ctx).grant(credits=Decimal(credits))


def _deduct(db: Session, ctx, event_id: str, cost_entry_id: str) -> None:
    row = _cost_event(event_id, cost_entry_id=cost_entry_id)
    row.tenant_id = ctx.tenant_id
    row.workspace_id = ctx.workspace_id
    row.payload_json = {
        **row.payload_json,
        "tenant_id": ctx.tenant_id,
        "workspace_id": ctx.workspace_id,
    }
    db.add(row)
    db.flush()
    handle_cost_recorded_credit(db, row)


def test_low_threshold_crossing_publishes_one_alert(db: Session, ctx) -> None:
    _grant(db, ctx, "300")  # deduction of 250 lands at 50, below the 100 default
    _deduct(db, ctx, "evt_cross_low", "cost_entry_cross_low")

    events = _balance_alert_events(db)
    assert len(events) == 1
    payload = events[0].payload_json
    assert payload["state"] == "low"
    assert payload["balance"] == "50.000000"

    # A further deduction that stays below the threshold does not re-alert
    # (until the balance is exhausted, which is a separate crossing).
    _deduct(db, ctx, "evt_cross_low_again", "cost_entry_cross_low_again")
    events = _balance_alert_events(db)
    assert {event.payload_json["state"] for event in events} == {"low", "exhausted"}


def test_exhaustion_crossing_publishes_error_alert(db: Session, ctx) -> None:
    _grant(db, ctx, "200")  # deduction of 250 lands at -50
    _deduct(db, ctx, "evt_cross_exhausted", "cost_entry_cross_exhausted")

    events = _balance_alert_events(db)
    assert len(events) == 1
    assert events[0].payload_json["state"] == "exhausted"

    # Already exhausted: further deductions do not spam alerts.
    _deduct(db, ctx, "evt_cross_exhausted_2", "cost_entry_cross_exhausted_2")
    assert len(_balance_alert_events(db)) == 1


def test_healthy_deduction_publishes_no_alert(db: Session, ctx) -> None:
    _grant(db, ctx, "1000")
    _deduct(db, ctx, "evt_no_cross", "cost_entry_no_cross")
    assert _balance_alert_events(db) == []


def test_balance_alert_notifies_owner_and_admin_only(db: Session, ctx) -> None:
    for user_id, role in (
        ("user_owner", "Owner"),
        ("user_admin", "Admin"),
        ("user_viewer", "Viewer"),
    ):
        db.add(
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
    db.add(event)
    db.flush()

    handle_credit_balance_low(db, event)
    handle_credit_balance_low(db, event)  # idempotent replay

    rows = list(db.exec(select(Notification)).all())
    notifications = [row if hasattr(row, "id") else row[0] for row in rows]
    assert {n.user_id for n in notifications} == {"user_owner", "user_admin"}
    assert all(n.type == "alert" for n in notifications)
    assert all(n.severity == "warning" for n in notifications)
    assert all(n.source_module == "billing" for n in notifications)
    assert all(n.meta["state"] == "low" for n in notifications)


def test_balance_status_reflects_enforcement_thresholds(db: Session, ctx, monkeypatch) -> None:
    monkeypatch.setattr(settings, "credit_enforcement_enabled", True)
    monkeypatch.setattr(settings, "credit_low_balance_threshold", 100.0)
    service = CreditService(db, ctx)

    assert service.get_balance().status == "exhausted"
    service.grant(credits=Decimal("50"))
    assert service.get_balance().status == "low"
    service.grant(credits=Decimal("500"))
    balance = service.get_balance()
    assert balance.status == "ok"
    assert balance.enforcement_enabled is True
    assert balance.low_balance_threshold == Decimal("100")
