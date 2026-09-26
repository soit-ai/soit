""" ledger

The runtime ledger as a contract.

Runs, run steps, cost entries, audit entries and outbox events leave SOIT
only as the records this module writes, each wrapped in an envelope naming
the contract version (``kernel/specs/v1/ledger_spec.schema.json``). Exports
and run evidence bundles are built from these records, so a reader parses one
shape whatever produced the file, and a change to the shape is a change to
the contract, reviewed as one.

Timestamps are UTC with a ``Z`` suffix, decimals are strings, and structured
fields (step metrics, event payloads) stay objects.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.kernel.runtime.db.models.audit import AuditEvent
from app.kernel.runtime.db.models.events import EventOutbox
from app.kernel.runtime.db.models.runs import Run, RunCostEntry, RunStep

LEDGER_SPEC = "ledger_spec"
LEDGER_SCHEMA_VERSION = "1.0"
RECORD_TYPES = ("run", "step", "cost", "audit", "event")


def iso_utc(value: datetime | None) -> str | None:
    """A stored timestamp as UTC ISO 8601; naive values are UTC already."""
    if value is None:
        return None
    if value.tzinfo is not None:
        value = value.astimezone(UTC).replace(tzinfo=None)
    return value.isoformat() + "Z"


def _decimal(value: Decimal | float | int | None) -> str | None:
    if value is None:
        return None
    return format(Decimal(str(value)).normalize(), "f")


def _object(value: Any) -> dict[str, Any] | None:
    return dict(value) if isinstance(value, Mapping) else None


def envelope(record_type: str, record: dict[str, Any]) -> dict[str, Any]:
    """Wrap one record with the contract version it was written in."""
    if record_type not in RECORD_TYPES:
        raise ValueError(f"Unknown ledger record type: {record_type}")
    return {"schema_version": LEDGER_SCHEMA_VERSION, "record_type": record_type, "record": record}


def run_record(run: Run) -> dict[str, Any]:
    return {
        "run_id": run.id,
        "tenant_id": run.tenant_id,
        "workspace_id": run.workspace_id,
        "user_id": run.user_id,
        "trace_id": run.trace_id,
        "request_id": run.request_id,
        "parent_run_id": run.parent_run_id,
        "source_run_id": run.source_run_id,
        "attempt_no": run.attempt_no,
        "mode": run.mode,
        "kind": run.kind,
        "subject_kind": run.subject_kind,
        "subject_id": run.subject_id,
        "subject_version_id": run.subject_version_id,
        "status": run.status,
        "sandbox": bool(run.sandbox),
        "source": run.source,
        "api_key_id": run.api_key_id,
        "input_summary": run.input_summary,
        "output_summary": run.output_summary,
        "started_at": iso_utc(run.started_at),
        "ended_at": iso_utc(run.ended_at),
        "duration_ms": run.duration_ms,
        "error_code": run.error_code,
        "error_message": run.error_message,
        "error_step_id": run.error_step_id,
        "created_at": iso_utc(run.created_at),
        "updated_at": iso_utc(run.updated_at),
    }


def step_record(step: RunStep) -> dict[str, Any]:
    return {
        "step_record_id": step.id,
        "run_id": step.run_id,
        "tenant_id": step.tenant_id,
        "workspace_id": step.workspace_id,
        "trace_id": step.trace_id,
        "step_id": step.step_id,
        "step_type": step.step_type,
        "node_id": step.node_id,
        "status": step.status,
        "input_summary": step.input_summary,
        "output_summary": step.output_summary,
        "metrics": _object(step.metrics_json),
        "error_code": step.error_code,
        "error_message": step.error_message,
        "error_details": _object(step.error_details),
        "started_at": iso_utc(step.started_at),
        "ended_at": iso_utc(step.ended_at),
        "created_at": iso_utc(step.created_at),
    }


def cost_record(entry: RunCostEntry) -> dict[str, Any]:
    return {
        "cost_entry_id": entry.id,
        "run_id": entry.run_id,
        "step_id": entry.step_id,
        "tenant_id": entry.tenant_id,
        "workspace_id": entry.workspace_id,
        "currency": entry.currency,
        "amount": _decimal(entry.amount),
        "pricing_snapshot": _object(entry.pricing_snapshot_json) or {},
        "billing_basis": entry.billing_basis,
        "billed_quantity": _decimal(entry.billed_quantity),
        "source_ref": entry.source_ref,
        "provider": entry.provider,
        "provider_id": entry.provider_id,
        "provider_slug": entry.provider_slug,
        "provider_kind": entry.provider_kind,
        "model_ref": entry.model_ref,
        "upstream_model": entry.upstream_model,
        "tool_ref": entry.tool_ref,
        "source_port": entry.source_port,
        "operation": entry.operation,
        "prompt_tokens": entry.prompt_tokens,
        "completion_tokens": entry.completion_tokens,
        "total_tokens": entry.total_tokens,
        "latency_ms": entry.latency_ms,
        "request_count": entry.request_count,
        "embedding_count": entry.embedding_count,
        "rerank_count": entry.rerank_count,
        "vector_count": entry.vector_count,
        "storage_bytes": entry.storage_bytes,
        "created_at": iso_utc(entry.created_at),
    }


def audit_record(event: AuditEvent) -> dict[str, Any]:
    """An entry of the append-only audit table, in or outside a run."""
    return {
        "audit_id": event.id,
        "tenant_id": event.tenant_id,
        "workspace_id": event.workspace_id,
        "event_type": event.event_type,
        "resource_type": event.resource_type,
        "resource_id": event.resource_id,
        "run_id": event.run_id,
        "step_id": event.step_id,
        "trace_id": event.trace_id,
        "outcome": event.outcome,
        "evidence_artifact_id": event.evidence_artifact_id,
        "operation": event.operation,
        "actor_user_id": event.actor_user_id,
        "subject_user_id": event.subject_user_id,
        "scope": event.scope,
        "payload": _object(event.payload_json) or {},
        "created_at": iso_utc(event.created_at),
    }


def event_record(row: EventOutbox) -> dict[str, Any]:
    """An outbox event without its delivery state (leases, attempts, errors)."""
    return {
        "outbox_id": row.id,
        "event_id": row.event_id,
        "event_type": row.event_type,
        "event_version": row.event_version,
        "tenant_id": row.tenant_id,
        "workspace_id": row.workspace_id,
        "idempotency_key": row.idempotency_key,
        "subject_type": row.subject_type,
        "subject_id": row.subject_id,
        "run_id": row.run_id,
        "task_id": row.task_id,
        "thread_id": row.thread_id,
        "workflow_run_id": row.workflow_run_id,
        "correlation_id": row.correlation_id,
        "causation_id": row.causation_id,
        "producer": row.producer,
        "payload": _object(row.payload_json),
        "headers": _object(row.headers_json),
        "status": row.status,
        "occurred_at": iso_utc(row.occurred_at),
        "created_at": iso_utc(row.created_at),
        "processed_at": iso_utc(row.processed_at),
    }
