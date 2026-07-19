"""Read-safe projections for durable runtime tool calls."""

from __future__ import annotations

from typing import Any

from sqlalchemy import and_, select

from app.kernel.commons.errors import KernelError
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.runs import RunStepToolCall

_PUBLIC_STATUS = {
    "claimed": "preparing",
    "in_doubt": "paused",
    "rejected": "canceled",
    "succeeded": "completed",
}


def _unwrap_row(value: Any) -> Any:
    if isinstance(value, tuple):
        return value[0]
    if hasattr(value, "_mapping") and len(value) == 1:
        return value[0]
    return value


def _step_metrics(step: Any) -> dict[str, Any]:
    metrics = getattr(step, "metrics_json", None)
    if not isinstance(metrics, dict):
        return {}
    tool_call = metrics.get("tool_call")
    return dict(tool_call) if isinstance(tool_call, dict) else {}


def _record_result(record: RunStepToolCall) -> dict[str, Any]:
    payload = record.result_json if isinstance(record.result_json, dict) else {}
    if "result" in payload:
        return {"result": payload.get("result")}
    artifact = payload.get("artifact")
    return {"artifact": artifact} if isinstance(artifact, dict) else {}


def project_run_tool_calls(
    *,
    db: Any,
    ctx: RequestContext,
    run_id: str,
    steps: list[Any],
    response_id: str,
    thread_id: str | None = None,
    task_id: str | None = None,
    agent_id: str | None = None,
) -> list[dict[str, Any]]:
    """Project one public tool-call item per durable control record."""

    step_by_id = {str(step.id): step for step in steps}
    rows = db.exec(
        select(RunStepToolCall)
        .where(
            and_(
                RunStepToolCall.run_id == run_id,
                RunStepToolCall.tenant_id == ctx.tenant_id,
                RunStepToolCall.workspace_id == ctx.workspace_id,
            )
        )
        .order_by(RunStepToolCall.created_at.asc(), RunStepToolCall.id.asc())
    ).all()
    records = [_unwrap_row(row) for row in rows]
    projections: list[dict[str, Any]] = []
    tool_step_ids = {
        str(step.id)
        for step in steps
        if getattr(step, "step_type", None) == "tool"
    }
    record_step_ids = {str(record.run_step_id) for record in records}
    missing_record_step_ids = sorted(tool_step_ids - record_step_ids)
    if missing_record_step_ids:
        raise KernelError(
            "RUNTIME_CONTRACT_VIOLATION",
            "Tool run step is missing a run_step_tool_calls record",
            {"run_id": run_id, "run_step_ids": missing_record_step_ids},
        )

    for record in records:
        step = step_by_id.get(record.run_step_id)
        if step is None:
            raise KernelError(
                "RUNTIME_CONTRACT_VIOLATION",
                "Tool-call control record references a missing run step",
                {
                    "run_id": run_id,
                    "run_step_tool_call_id": record.id,
                    "run_step_id": record.run_step_id,
                },
            )
        tool_metrics = _step_metrics(step)
        result_payload = record.result_json if isinstance(record.result_json, dict) else {}
        result_metadata = result_payload.get("metadata")
        metadata = dict(tool_metrics.get("metadata") or {})
        if isinstance(result_metadata, dict):
            metadata.update(result_metadata)
        projections.append(
            {
                "id": step.id,
                "run_step_tool_call_id": record.id,
                "tool_call_id": record.tool_call_id,
                "attempt_count": record.attempt_count,
                "result_artifact_id": record.result_artifact_id,
                "tenant_id": record.tenant_id,
                "workspace_id": record.workspace_id,
                "response_id": response_id,
                "run_id": run_id,
                "step_id": step.id,
                "thread_id": thread_id,
                "task_id": task_id,
                "agent_id": agent_id,
                "tool_name": record.tool_ref,
                "tool_type": tool_metrics.get("tool_type", "builtin"),
                "status": _PUBLIC_STATUS.get(record.status, record.status),
                "arguments_json": tool_metrics.get("arguments")
                or record.parameters_summary_json
                or {},
                "result_json": _record_result(record),
                "metadata_json": metadata,
                "error_code": record.error_code or getattr(step, "error_code", None),
                "error_message": record.error_message or getattr(step, "error_message", None),
                "started_at": record.outbound_started_at or getattr(step, "started_at", None),
                "completed_at": record.completed_at or getattr(step, "ended_at", None),
                "created_at": record.created_at,
                "updated_at": record.updated_at,
            }
        )

    return projections


__all__ = ["project_run_tool_calls"]
