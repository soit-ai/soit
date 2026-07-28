"""Credit ledger: deduction consumer idempotency, conversion, and service math."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlmodel import Session, select

from app.kernel.runtime.db.models.events import EventOutbox
from app.modules.billing.application.service import CreditService
from app.modules.billing.domain.models import CreditLedgerEntry
from app.modules.billing.handlers.on_cost_recorded import handle_cost_recorded_credit


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


def test_unpriced_and_unsupported_currency_events_book_nothing(db: Session) -> None:
    unpriced = _cost_event("evt_cost_credit_unpriced", amount=None, currency=None)
    unsupported = _cost_event(
        "evt_cost_credit_eur", cost_entry_id="cost_entry_eur", currency="EUR"
    )
    db.add(unpriced)
    db.add(unsupported)
    db.flush()

    handle_cost_recorded_credit(db, unpriced)
    handle_cost_recorded_credit(db, unsupported)

    assert _ledger_rows(db) == []


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
