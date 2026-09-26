"""The ledger leaves SOIT only in the shape its contract states.

The drift checks here are the contract review: a column added to a ledger
model fails them until the contract names it (a new optional field) or the
test records why it stays inside (operational state no reader should rely
on). Silently growing an export is not possible.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.kernel.commons.errors import ValidationError
from app.kernel.runtime.db.models.events import EventOutbox
from app.kernel.runtime.db.models.runs import Run, RunCostEntry, RunStep
from app.kernel.runtime.runs import ledger
from app.kernel.runtime.runs.schemas import RunAuditLogResponse
from app.kernel.specs import load_schema, validate_spec

NOW = datetime(2026, 9, 27, 10, 30, 15, 123456)

# Model column -> contract field, where the names differ.
RENAMED = {
    "runs": {"id": "run_id"},
    "run_steps": {"id": "step_record_id", "metrics_json": "metrics"},
    "run_cost_entries": {"id": "cost_entry_id", "pricing_snapshot_json": "pricing_snapshot"},
    "event_outbox": {"id": "outbox_id", "payload_json": "payload", "headers_json": "headers"},
}
# Columns that stay inside: delivery state of the outbox, not facts of the ledger.
INTERNAL = {
    "event_outbox": {
        "available_at",
        "locked_at",
        "lock_owner",
        "lock_expires_at",
        "attempt_count",
        "last_error",
        "failed_consumer_name",
    },
}
MODELS = {"run": Run, "step": RunStep, "cost": RunCostEntry, "event": EventOutbox}


def _contract_fields(record_type: str) -> set[str]:
    return set(load_schema(ledger.LEDGER_SPEC)["$defs"][record_type]["properties"])


def _run() -> Run:
    return Run(
        id="run_ledger",
        tenant_id="t1",
        workspace_id="w1",
        user_id="u1",
        mode="gateway",
        kind="chat",
        status="succeeded",
        source="gateway",
        api_key_id="key_1",
        input_summary="model=model:test:chat",
        started_at=NOW,
        ended_at=NOW,
        duration_ms=12,
        created_at=NOW,
        updated_at=NOW,
    )


def _step() -> RunStep:
    return RunStep(
        id="step_ledger",
        tenant_id="t1",
        workspace_id="w1",
        run_id="run_ledger",
        step_id="llm",
        step_type="llm",
        status="succeeded",
        metrics_json={"tokens_prompt": 3, "model_ref": "model:test:chat"},
        started_at=NOW,
        created_at=NOW,
    )


def _cost() -> RunCostEntry:
    return RunCostEntry(
        id="ce_ledger",
        run_id="run_ledger",
        step_id="step_ledger",
        tenant_id="t1",
        workspace_id="w1",
        currency="USD",
        amount=Decimal("0.001200"),
        pricing_snapshot_json={"input": 1.2},
        billing_basis="tokens",
        billed_quantity=Decimal("15"),
        provider="openai",
        model_ref="model:openai:gpt-5.5",
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        created_at=NOW,
    )


def _event() -> EventOutbox:
    return EventOutbox(
        id="obx_ledger",
        event_id="evt_ledger",
        event_type="run.created",
        event_version="1",
        idempotency_key="evt_ledger",
        tenant_id="t1",
        workspace_id="w1",
        run_id="run_ledger",
        payload_json={"run_id": "run_ledger"},
        status="processed",
        occurred_at=NOW,
        created_at=NOW,
        processed_at=NOW.replace(tzinfo=UTC),
    )


def _audit() -> RunAuditLogResponse:
    return RunAuditLogResponse(
        run_id="run_ledger",
        step_id="step_ledger",
        step_type="tool",
        audit_id="aud_1",
        outcome="allowed",
        gateway_type="tool",
        request={"tool_ref": "builtin.http"},
        response={"success": True},
        actor_user_id="u1",
        created_at=NOW,
    )


RECORDS = {
    "run": lambda: ledger.run_record(_run()),
    "step": lambda: ledger.step_record(_step()),
    "cost": lambda: ledger.cost_record(_cost()),
    "audit": lambda: ledger.audit_record(_audit()),
    "event": lambda: ledger.event_record(_event()),
}


@pytest.mark.parametrize("record_type", ledger.RECORD_TYPES)
def test_every_record_validates_against_the_contract(record_type: str) -> None:
    document = ledger.envelope(record_type, RECORDS[record_type]())

    assert validate_spec(document, ledger.LEDGER_SPEC) is True
    assert document["schema_version"] == ledger.LEDGER_SCHEMA_VERSION


@pytest.mark.parametrize("record_type", ledger.RECORD_TYPES)
def test_the_writer_and_the_contract_name_the_same_fields(record_type: str) -> None:
    assert set(RECORDS[record_type]()) == _contract_fields(record_type)


@pytest.mark.parametrize("record_type", sorted(MODELS))
def test_every_ledger_column_is_in_the_contract_or_kept_inside_on_purpose(
    record_type: str,
) -> None:
    table = MODELS[record_type].__table__
    renamed = RENAMED.get(table.name, {})
    internal = INTERNAL.get(table.name, set())

    published = {renamed.get(column.name, column.name) for column in table.columns} - internal

    assert published == _contract_fields(record_type), (
        "A ledger column changed: add it to kernel/specs/v1/ledger_spec.schema.json "
        "(and ledger.py) or list it as internal here, with the reason."
    )


def test_the_contract_version_is_the_writer_version() -> None:
    schema = load_schema(ledger.LEDGER_SPEC)

    assert schema["properties"]["schema_version"]["const"] == ledger.LEDGER_SCHEMA_VERSION


def test_values_that_would_lose_meaning_are_refused() -> None:
    record = ledger.cost_record(_cost())

    assert record["amount"] == "0.0012"
    assert record["created_at"] == "2026-09-27T10:30:15.123456Z"
    # A float amount is a rounding waiting to happen; the contract refuses it.
    with pytest.raises(ValidationError):
        validate_spec(ledger.envelope("cost", {**record, "amount": 0.0012}), ledger.LEDGER_SPEC)
    with pytest.raises(ValidationError):
        validate_spec(ledger.envelope("run", {**ledger.run_record(_run()), "extra": 1}), ledger.LEDGER_SPEC)


def test_an_aware_timestamp_is_written_in_utc() -> None:
    assert ledger.event_record(_event())["processed_at"] == "2026-09-27T10:30:15.123456Z"
    assert ledger.iso_utc(None) is None
