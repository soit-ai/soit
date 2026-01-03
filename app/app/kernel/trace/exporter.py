""" exporter

Trace exporters to observability stack.

The exporter is intentionally lightweight and does not require external deps.
In production you can swap it with a real OpenTelemetry/Jaeger/Tempo exporter.

Current implementation:
- Converts Run/RunStep (+ optional artifacts/cost) into runtrace spec
- Emits structured logs for downstream collection
"""

from __future__ import annotations

from typing import Optional, Dict, Any
import json
import logging

from app.kernel.trace.models import Run, RunStep, RunArtifact, RunCost
from app.kernel.commons.time import to_iso8601


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
            "status": run.status,
            "created_at": to_iso8601(run.created_at) if run.created_at else None,
            "updated_at": to_iso8601(run.updated_at) if run.updated_at else None,
            "type": run.run_type,
        }
        self._emit("run", payload)

    def export_step(self, step: RunStep) -> None:
        """Export step."""
        payload = {
            "run_id": step.run_id,
            "step_id": step.id,
            "type": step.step_type,
            "status": step.status,
            "created_at": to_iso8601(step.created_at) if step.created_at else None,
            "updated_at": to_iso8601(step.updated_at) if step.updated_at else None,
            "metrics": step.metrics_json or {},
        }
        self._emit("step", payload)

    def _emit(self, kind: str, payload: Dict[str, Any]) -> None:
        try:
            self.logger.info("otel.%s %s", kind, json.dumps(payload, ensure_ascii=False, default=str))
        except Exception:
            self.logger.info("otel.%s %s", kind, payload)


def to_runtrace_spec(
    run: Run,
    steps: list[RunStep],
    artifacts: Optional[list[RunArtifact]] = None,
    cost: Optional[RunCost] = None,
) -> Dict[str, Any]:
    """Convert run objects to RunTraceSpec-like dict."""
    spec: Dict[str, Any] = {
        "id": run.id,
        "tenant_id": run.tenant_id,
        "workspace_id": run.workspace_id,
        "type": run.run_type,
        "status": run.status,
        "created_at": to_iso8601(run.created_at) if run.created_at else None,
        "updated_at": to_iso8601(run.updated_at) if run.updated_at else None,
        "inputs": run.inputs_json or {},
        "outputs": run.outputs_json or {},
        "metadata": run.metadata_json or {},
        "steps": [to_step_spec(s) for s in steps],
    }

    if artifacts:
        spec["artifacts"] = [
            {
                "id": a.id,
                "kind": a.artifact_type,
                "name": a.name,
                "mime_type": a.mime_type,
                "size_bytes": a.size_bytes,
                "uri": a.uri,
                "created_at": to_iso8601(a.created_at) if a.created_at else None,
            }
            for a in artifacts
        ]

    if cost:
        spec["cost"] = {
            "tokens_prompt": cost.tokens_prompt,
            "tokens_completion": cost.tokens_completion,
            "embedding_count": cost.embedding_count,
            "rerank_count": cost.rerank_count,
            "ms_total": cost.ms_total,
            "storage_bytes": cost.storage_bytes,
        }

    return spec


def to_step_spec(step: RunStep) -> Dict[str, Any]:
    return {
        "id": step.id,
        "run_id": step.run_id,
        "type": step.step_type,
        "status": step.status,
        "created_at": to_iso8601(step.created_at) if step.created_at else None,
        "updated_at": to_iso8601(step.updated_at) if step.updated_at else None,
        "inputs": step.inputs_json or {},
        "outputs": step.outputs_json or {},
        "metrics": step.metrics_json or {},
        "metadata": step.metadata_json or {},
        "error": step.error_json or None,
    }
