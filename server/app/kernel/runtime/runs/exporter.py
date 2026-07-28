""" exporter

Trace exporters to observe stack.

The exporter is intentionally lightweight and does not require external deps.
In production you can swap it with a real OpenTelemetry/Jaeger/Tempo exporter.

Current implementation:
- Converts Run/RunStep (+ optional artifacts/cost) into runtrace spec
- Emits structured logs for downstream collection
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.kernel.commons.time import to_iso8601
from app.kernel.runtime.db.models.runs import Run, RunArtifact, RunCostEntry, RunStep

logger = logging.getLogger(__name__)


class OpenTelemetryExporter:
    """Export trace data as structured logs (OTel compatible payload)."""

    def __init__(self) -> None:
        """Initialize exporter."""
        # Keep constructor side-effect free for testability
        self.logger = logger

    def export_run(self, run: Run) -> None:
        """Export run.

        For now we emit JSON logs so any log-collector can pick them up.
        """
        payload = {
            "run_id": run.id,
            "tenant_id": run.tenant_id,
            "workspace_id": run.workspace_id,
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
            "started_at": to_iso8601(run.started_at) if run.started_at else None,
            "ended_at": to_iso8601(run.ended_at) if run.ended_at else None,
            "duration_ms": run.duration_ms,
            "input_summary": run.input_summary,
            "output_summary": run.output_summary,
            "error_code": run.error_code,
            "error_message": run.error_message,
            "error_step_id": run.error_step_id,
        }
        self._emit("run", payload)

    def export_step(self, step: RunStep) -> None:
        """Export step."""
        payload = {
            "run_id": step.run_id,
            "step_id": step.id,
            "step_type": step.step_type,
            "status": step.status,
            "started_at": to_iso8601(step.started_at) if step.started_at else None,
            "ended_at": to_iso8601(step.ended_at) if step.ended_at else None,
            "metrics": step.metrics_json or {},
            "input_summary": step.input_summary,
            "output_summary": step.output_summary,
            "error_code": step.error_code,
            "error_message": step.error_message,
        }
        self._emit("step", payload)

    def _emit(self, kind: str, payload: dict[str, Any]) -> None:
        try:
            self.logger.info("otel.%s %s", kind, json.dumps(payload, ensure_ascii=False, default=str))
        except Exception:
            self.logger.info("otel.%s %s", kind, payload)


def to_runtrace_spec(
    run: Run,
    steps: list[RunStep],
    artifacts: list[RunArtifact] | None = None,
    cost_entries: list[RunCostEntry] | None = None,
) -> dict[str, Any]:
    """Convert run objects to RunTraceSpec-like dict."""
    spec: dict[str, Any] = {
        "run": {
            "run_id": run.id,
            "tenant_id": run.tenant_id,
            "workspace_id": run.workspace_id,
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
            "input_summary": run.input_summary,
            "output_summary": run.output_summary,
            "started_at": to_iso8601(run.started_at) if run.started_at else None,
            "ended_at": to_iso8601(run.ended_at) if run.ended_at else None,
            "duration_ms": run.duration_ms,
            "error_code": run.error_code,
            "error_message": run.error_message,
            "error_step_id": run.error_step_id,
        },
        "steps": [to_step_spec(s) for s in steps],
    }

    if artifacts:
        spec["artifacts"] = [
            {
                "artifact_id": a.id,
                "type": a.type,
                "storage_key": a.storage_key,
                "step_id": a.step_id,
                "mime": a.mime,
                "size_bytes": a.size_bytes,
                "sha256": a.sha256,
                "meta": a.meta_json or {},
            }
            for a in artifacts
        ]

    if cost_entries is not None:
        usage_entries = [entry for entry in cost_entries if entry.entry_type == "usage"]
        priced_entries = [entry for entry in cost_entries if entry.amount is not None]
        spec["usage_summary"] = _summarize_entries(usage_entries)
        charge_amounts: dict[str, float] = {}
        for entry in priced_entries:
            if entry.currency and entry.amount is not None:
                charge_amounts[entry.currency] = charge_amounts.get(entry.currency, 0.0) + float(entry.amount)
        spec["charge_summary"] = {
            "entry_count": len(priced_entries),
            "amounts": charge_amounts,
        }
        spec["entries"] = [
            {
                "cost_id": entry.id,
                "run_id": entry.run_id,
                "step_id": entry.step_id,
                "entry_type": entry.entry_type,
                "currency": entry.currency,
                "amount": float(entry.amount) if entry.amount is not None else None,
                "pricing_snapshot_json": entry.pricing_snapshot_json,
                "unit": entry.unit,
                "quantity": float(entry.quantity),
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
                "created_at": to_iso8601(entry.created_at) if entry.created_at else None,
            }
            for entry in cost_entries
        ]

    return spec


def to_step_spec(step: RunStep) -> dict[str, Any]:
    return {
        "step_id": step.id,
        "node_id": step.node_id,
        "step_type": step.step_type,
        "status": step.status,
        "input_summary": step.input_summary,
        "output_summary": step.output_summary,
        "started_at": to_iso8601(step.started_at) if step.started_at else None,
        "ended_at": to_iso8601(step.ended_at) if step.ended_at else None,
        "metrics": step.metrics_json or {},
        "error": {
            "code": step.error_code,
            "message": step.error_message,
            "details": step.error_details,
        } if step.error_code or step.error_message or step.error_details else None,
    }


def _summarize_entries(entries: list[RunCostEntry]) -> dict[str, Any]:
    summary = {
        "tokens_prompt": 0,
        "tokens_completion": 0,
        "embedding_count": 0,
        "rerank_count": 0,
        "ms_total": 0,
        "storage_bytes": 0,
        "request_count": 0,
        "vector_count": 0,
    }
    for entry in entries:
        summary["tokens_prompt"] += int(entry.prompt_tokens or 0)
        summary["tokens_completion"] += int(entry.completion_tokens or 0)
        summary["embedding_count"] += int(entry.embedding_count or 0)
        summary["rerank_count"] += int(entry.rerank_count or 0)
        summary["ms_total"] += int(entry.latency_ms or 0)
        summary["storage_bytes"] += int(entry.storage_bytes or 0)
        summary["request_count"] += int(entry.request_count or 0)
        summary["vector_count"] += int(entry.vector_count or 0)
    return summary
