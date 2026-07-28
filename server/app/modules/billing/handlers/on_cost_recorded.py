"""Credit deduction consumer for COST_RECORDED outbox events.

Deductions are derived valuation only: the ledger row references the
priced run_cost_entries row via cost_entry_id and never copies measured
usage. Idempotency is layered - the consumer checkpoint dedupes per
event, and the unique cost_entry_id index makes double-booking a
constraint violation even if an unexpected duplicate event slips through.
"""

from __future__ import annotations

import json
import logging
from decimal import Decimal, InvalidOperation

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.kernel.events.checkpoint import try_claim_consumer_slot
from app.kernel.runtime.db.models.events import EventOutbox
from app.modules.billing.domain.models import CreditLedgerEntry
from app.settings.settings import settings

logger = logging.getLogger(__name__)

CONSUMER_NAME = "billing.credit.deduction"
CREATED_BY = "system:credit-deduction"


def _credit_rates() -> dict[str, Decimal]:
    try:
        raw = json.loads(settings.credit_rates_json)
    except (TypeError, ValueError):
        logger.warning("credit_rates_json is not valid JSON; credit deduction disabled")
        return {}
    rates: dict[str, Decimal] = {}
    if isinstance(raw, dict):
        for currency, rate in raw.items():
            try:
                rates[str(currency)] = Decimal(str(rate))
            except (InvalidOperation, TypeError, ValueError):
                logger.warning("Ignoring invalid credit rate for %s: %r", currency, rate)
    return rates


def _decimal_or_none(value: object) -> Decimal | None:
    if value is None:
        return None
    text = str(value)
    if text in ("", "None"):
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def handle_cost_recorded_credit(db: Session, row: EventOutbox) -> None:
    """Book one credit deduction for a priced usage row, exactly once."""
    if not try_claim_consumer_slot(
        db,
        consumer_name=CONSUMER_NAME,
        event_id=row.event_id,
        result="credit_deduction",
    ):
        return

    payload = row.payload_json or {}
    cost_entry_id = payload.get("cost_entry_id")
    tenant_id = payload.get("tenant_id") or row.tenant_id
    workspace_id = payload.get("workspace_id") or row.workspace_id
    if not cost_entry_id or not tenant_id or not workspace_id:
        return

    amount = _decimal_or_none(payload.get("amount"))
    currency = payload.get("currency")
    if amount is None or amount <= 0 or not currency:
        return

    rate = _credit_rates().get(str(currency))
    if rate is None:
        # Unknown currencies must still leave ledger evidence: a zero-credit
        # adjustment keeps the priced amount auditable and repricable later.
        logger.warning(
            "No credit rate configured for currency %s; booking zero-credit adjustment for %s",
            currency,
            cost_entry_id,
        )
        entry = CreditLedgerEntry(
            tenant_id=str(tenant_id),
            workspace_id=str(workspace_id),
            kind="adjustment",
            credits_delta=Decimal("0"),
            cost_entry_id=str(cost_entry_id),
            run_id=payload.get("run_id"),
            currency=str(currency),
            amount=amount,
            conversion_snapshot_json={
                "schema_version": 1,
                "source_event_id": row.event_id,
                "reason": "no_rate_configured_for_currency",
                "amount": format(amount, "f"),
                "credits": "0",
            },
            note=f"No credit rate configured for currency {currency}",
            created_by=CREATED_BY,
        )
    else:
        credits = (amount * rate).quantize(Decimal("0.000001"))
        entry = CreditLedgerEntry(
            tenant_id=str(tenant_id),
            workspace_id=str(workspace_id),
            kind="deduction",
            credits_delta=-credits,
            cost_entry_id=str(cost_entry_id),
            run_id=payload.get("run_id"),
            currency=str(currency),
            amount=amount,
            conversion_snapshot_json={
                "schema_version": 1,
                "source_event_id": row.event_id,
                "rate": format(rate, "f"),
                "rate_basis": "credits_per_currency_unit",
                "amount": format(amount, "f"),
                "credits": format(credits, "f"),
            },
            created_by=CREATED_BY,
        )
    try:
        with db.begin_nested():
            db.add(entry)
            db.flush()
    except IntegrityError:
        logger.warning(
            "Credit deduction already booked for cost entry %s; skipping duplicate",
            cost_entry_id,
        )
