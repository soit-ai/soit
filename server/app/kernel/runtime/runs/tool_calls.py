"""Crash-aware execution control for governed runtime tool calls."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.kernel.commons.errors import ConflictError
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.storage.interface import StoragePort
from app.kernel.ports.tools.interface import ToolResponse
from app.kernel.runtime.db.models.runs import Run, RunArtifact, RunStep, RunStepToolCall
from app.kernel.runtime.runs.writer import TraceWriter

_SENSITIVE_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "access_token",
        "authorization",
        "client_secret",
        "cookie",
        "credential",
        "password",
        "private_key",
        "refresh_token",
        "secret",
        "secret_access_key",
        "session_token",
        "token",
        "x_api_key",
    }
)


def _normalized_parameter_key(value: Any) -> str:
    with_word_boundaries = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", str(value))
    return re.sub(r"[^a-z0-9]+", "_", with_word_boundaries.lower()).strip("_")


def _json_payload(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def canonical_request_hash(value: Any) -> str:
    payload = json.dumps(value or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _redact_tool_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): (
                "[REDACTED]"
                if _normalized_parameter_key(key) in _SENSITIVE_KEYS
                and not (
                    isinstance(child, dict)
                    and isinstance(child.get("secret_ref"), str)
                )
                else _redact_tool_payload(child)
            )
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [_redact_tool_payload(child) for child in value]
    return _json_payload(value)


def summarize_tool_payload(value: Any) -> Any:
    """Return a redacted, size-bounded representation for persisted tool data."""

    redacted = _redact_tool_payload(value)
    encoded = json.dumps(redacted, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    if len(encoded) <= 8192:
        return redacted
    return {
        "truncated": True,
        "size_bytes": len(encoded),
        "payload_hash": canonical_request_hash(value),
    }


def summarize_parameters(value: dict[str, Any]) -> dict[str, Any]:
    summary = summarize_tool_payload(value)
    if not isinstance(summary, dict) or not summary.get("truncated"):
        return summary if isinstance(summary, dict) else {"value": summary}
    return {
        "truncated": True,
        "size_bytes": summary["size_bytes"],
        "request_hash": summary["payload_hash"],
        "argument_names": sorted(str(key) for key in value),
    }


def _aware_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


@dataclass(frozen=True)
class ToolExecutionCommand:
    """Stable identity and input for one logical runtime tool call."""

    run_id: str
    tool_call_id: str
    tool_ref: str
    arguments: dict[str, Any]
    idempotency_key: str
    run_step_id: str | None = None
    created_by: str | None = None
    resume_approval: bool = False
    retry_failed: bool = False


@dataclass(frozen=True)
class ToolExecutionClaim:
    """Claimed execution state returned to a governed tool gateway."""

    record: RunStepToolCall
    run_step: RunStep
    replayed: bool = False
    cached_response: ToolResponse | None = None


class RuntimeToolExecutionService:
    """Own the durable tool-call claim and its RunStep lifecycle."""

    def __init__(
        self,
        *,
        db: Session,
        ctx: RequestContext,
        trace_writer: TraceWriter,
        lease_owner: str,
        lease_seconds: int = 60,
        storage_port: StoragePort | None = None,
    ) -> None:
        self.db = db
        self.ctx = ctx
        self.trace_writer = trace_writer
        self.lease_owner = lease_owner
        self.lease_seconds = lease_seconds
        self.storage_port = storage_port

    def _require_run(self, run_id: str) -> Run:
        run = self.db.get(Run, run_id)
        if (
            run is None
            or run.tenant_id != self.ctx.tenant_id
            or run.workspace_id != self.ctx.workspace_id
        ):
            raise ValueError("Run scope mismatch")
        return run

    def _require_tool_step(self, *, run_id: str, run_step_id: str) -> RunStep:
        step = self.db.get(RunStep, run_step_id)
        if (
            step is None
            or step.tenant_id != self.ctx.tenant_id
            or step.workspace_id != self.ctx.workspace_id
            or step.run_id != run_id
            or step.step_type != "tool"
        ):
            raise ValueError("Tool RunStep scope mismatch")
        return step

    def _find_existing(
        self,
        command: ToolExecutionCommand,
        *,
        for_update: bool = False,
    ) -> RunStepToolCall | None:
        statement = select(RunStepToolCall).where(
                and_(
                    RunStepToolCall.tenant_id == self.ctx.tenant_id,
                    RunStepToolCall.workspace_id == self.ctx.workspace_id,
                    RunStepToolCall.run_id == command.run_id,
                    RunStepToolCall.tool_call_id == command.tool_call_id,
                )
            )
        if for_update:
            statement = statement.with_for_update()
        return self.db.execute(statement).scalars().first()

    def get_by_call(self, *, run_id: str, tool_call_id: str) -> ToolExecutionClaim | None:
        """Return the scoped control record and linked step for a logical call."""

        record = self.db.execute(
            select(RunStepToolCall).where(
                and_(
                    RunStepToolCall.tenant_id == self.ctx.tenant_id,
                    RunStepToolCall.workspace_id == self.ctx.workspace_id,
                    RunStepToolCall.run_id == run_id,
                    RunStepToolCall.tool_call_id == tool_call_id,
                )
            )
        ).scalars().first()
        if record is None:
            return None
        step = self._require_tool_step(run_id=record.run_id, run_step_id=record.run_step_id)
        return ToolExecutionClaim(record=record, run_step=step)

    def _require_record(self, record_id: str) -> RunStepToolCall:
        record = self.db.get(RunStepToolCall, record_id)
        if (
            record is None
            or record.tenant_id != self.ctx.tenant_id
            or record.workspace_id != self.ctx.workspace_id
        ):
            raise ValueError("Tool-call record scope mismatch")
        return record

    def claim(self, command: ToolExecutionCommand) -> ToolExecutionClaim:
        """Create the RunStep and atomically claim one logical tool call."""

        self._require_run(command.run_id)
        request_hash = canonical_request_hash(command.arguments)
        existing = self._find_existing(command, for_update=True)
        if existing is not None:
            if (
                existing.tool_ref != command.tool_ref
                or existing.idempotency_key != command.idempotency_key
            ):
                raise ConflictError("Tool call identity was reused with different input")
            if existing.status == "waiting_approval" and command.resume_approval:
                now = utc_now()
                existing.request_hash = request_hash
                existing.parameters_summary_json = summarize_parameters(command.arguments)
                existing.status = "claimed"
                existing.attempt_count = max(existing.attempt_count, 0) + 1
                existing.lease_owner = self.lease_owner
                existing.lease_expires_at = now + timedelta(seconds=self.lease_seconds)
                existing.updated_at = now
                self.db.add(existing)
                self.db.commit()
                self.db.refresh(existing)
                step = self._require_tool_step(
                    run_id=existing.run_id,
                    run_step_id=existing.run_step_id,
                )
                return ToolExecutionClaim(record=existing, run_step=step)
            if existing.request_hash != request_hash:
                raise ConflictError("Tool call identity was reused with different input")
            if (
                existing.status in {"claimed", "running"}
                and existing.lease_owner == self.lease_owner
                and existing.lease_expires_at is not None
                and _aware_utc(existing.lease_expires_at) > utc_now()
            ):
                step = self._require_tool_step(
                    run_id=existing.run_id,
                    run_step_id=existing.run_step_id,
                )
                return ToolExecutionClaim(record=existing, run_step=step)
            if existing.status == "failed" and command.retry_failed:
                now = utc_now()
                step = self._require_tool_step(
                    run_id=existing.run_id,
                    run_step_id=existing.run_step_id,
                )
                self.trace_writer.update_step_status(step.id, "retrying")
                existing.status = "claimed"
                existing.attempt_count += 1
                existing.lease_owner = self.lease_owner
                existing.lease_expires_at = now + timedelta(seconds=self.lease_seconds)
                existing.outbound_started_at = None
                existing.result_json = {}
                existing.result_artifact_id = None
                existing.error_code = None
                existing.error_message = None
                existing.updated_at = now
                existing.completed_at = None
                self.db.add(existing)
                self.db.commit()
                self.db.refresh(existing)
                self.db.refresh(step)
                return ToolExecutionClaim(record=existing, run_step=step)
            if existing.status in {"succeeded", "failed"}:
                payload = existing.result_json or {}
                step = self._require_tool_step(
                    run_id=existing.run_id,
                    run_step_id=existing.run_step_id,
                )
                return ToolExecutionClaim(
                    record=existing,
                    run_step=step,
                    replayed=True,
                    cached_response=ToolResponse(
                        result=payload.get("result"),
                        success=existing.status == "succeeded",
                        error=existing.error_message,
                        metadata={
                            **dict(payload.get("metadata") or {}),
                            "idempotent_replay": True,
                        },
                    ),
                )
            if existing.status == "in_doubt":
                raise ConflictError("Tool call outcome is in doubt")
            now = utc_now()
            lease_expired = (
                existing.lease_expires_at is not None
                and _aware_utc(existing.lease_expires_at) <= now
            )
            if lease_expired and existing.outbound_started_at is not None:
                existing.status = "in_doubt"
                existing.lease_owner = None
                existing.lease_expires_at = None
                existing.updated_at = now
                step = self._require_tool_step(
                    run_id=existing.run_id,
                    run_step_id=existing.run_step_id,
                )
                if step.status == "running":
                    self.trace_writer.update_step_status(
                        step.id,
                        "paused",
                        metrics={
                            "tool_call": {
                                "tool_call_id": existing.tool_call_id,
                                "tool_ref": existing.tool_ref,
                                "attempt_count": existing.attempt_count,
                                "operational_status": "in_doubt",
                            }
                        },
                    )
                self.db.add(existing)
                self.db.commit()
                raise ConflictError("Tool call outcome is in doubt")
            if lease_expired and existing.outbound_started_at is None:
                existing.status = "claimed"
                existing.attempt_count += 1
                existing.lease_owner = self.lease_owner
                existing.lease_expires_at = now + timedelta(seconds=self.lease_seconds)
                existing.updated_at = now
                self.db.add(existing)
                self.db.commit()
                self.db.refresh(existing)
                step = self._require_tool_step(
                    run_id=existing.run_id,
                    run_step_id=existing.run_step_id,
                )
                return ToolExecutionClaim(record=existing, run_step=step)
            raise ConflictError("Tool call is already claimed")

        if command.run_step_id:
            run_step = self._require_tool_step(
                run_id=command.run_id,
                run_step_id=command.run_step_id,
            )
        else:
            run_step = self.trace_writer.create_step(
                run_id=command.run_id,
                step_type="tool",
                input_summary=f"tool={command.tool_ref}",
            )
        if run_step.status == "queued":
            run_step = self.trace_writer.update_step_status(run_step.id, "preparing")

        now = utc_now()
        record = RunStepToolCall(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            run_id=command.run_id,
            run_step_id=run_step.id,
            tool_call_id=command.tool_call_id,
            idempotency_key=command.idempotency_key,
            request_hash=request_hash,
            tool_ref=command.tool_ref,
            status="claimed",
            attempt_count=1,
            lease_owner=self.lease_owner,
            lease_expires_at=now + timedelta(seconds=self.lease_seconds),
            parameters_summary_json=summarize_parameters(command.arguments),
            created_by=command.created_by or self.ctx.user_id,
            created_at=now,
            updated_at=now,
        )
        self.db.add(record)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            concurrent = self._find_existing(command)
            if concurrent is not None:
                raise ConflictError("Tool call is already claimed") from exc
            raise
        self.db.refresh(record)
        self.db.refresh(run_step)
        return ToolExecutionClaim(record=record, run_step=run_step)

    def prepare_waiting_approval(self, command: ToolExecutionCommand) -> ToolExecutionClaim:
        """Persist a tool-call intent before a required human approval."""

        self._require_run(command.run_id)
        existing = self._find_existing(command, for_update=True)
        request_hash = canonical_request_hash(command.arguments)
        if existing is not None:
            if (
                existing.tool_ref != command.tool_ref
                or existing.idempotency_key != command.idempotency_key
                or existing.request_hash != request_hash
            ):
                raise ConflictError("Tool call identity was reused with different input")
            if existing.status != "waiting_approval":
                raise ConflictError(f"Tool call cannot wait for approval from {existing.status!r}")
            step = self._require_tool_step(
                run_id=existing.run_id,
                run_step_id=existing.run_step_id,
            )
            return ToolExecutionClaim(record=existing, run_step=step)

        if command.run_step_id:
            run_step = self._require_tool_step(
                run_id=command.run_id,
                run_step_id=command.run_step_id,
            )
        else:
            run_step = self.trace_writer.create_step(
                run_id=command.run_id,
                step_type="tool",
                input_summary=f"tool={command.tool_ref}",
            )
        if run_step.status == "queued":
            run_step = self.trace_writer.update_step_status(run_step.id, "preparing")
        if run_step.status == "preparing":
            run_step = self.trace_writer.update_step_status(run_step.id, "waiting_approval")

        now = utc_now()
        record = RunStepToolCall(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            run_id=command.run_id,
            run_step_id=run_step.id,
            tool_call_id=command.tool_call_id,
            idempotency_key=command.idempotency_key,
            request_hash=request_hash,
            tool_ref=command.tool_ref,
            status="waiting_approval",
            attempt_count=0,
            parameters_summary_json=summarize_parameters(command.arguments),
            created_by=command.created_by or self.ctx.user_id,
            created_at=now,
            updated_at=now,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        self.db.refresh(run_step)
        return ToolExecutionClaim(record=record, run_step=run_step)

    def reject_approval(self, command: ToolExecutionCommand) -> ToolExecutionClaim:
        """Cancel a waiting tool call without crossing the outbound boundary."""

        existing = self._find_existing(command, for_update=True)
        if existing is None:
            raise ValueError("Waiting tool call not found")
        if (
            existing.tool_ref != command.tool_ref
            or existing.idempotency_key != command.idempotency_key
        ):
            raise ConflictError("Tool call identity was reused with different input")
        if existing.status != "waiting_approval":
            raise ConflictError(f"Tool call cannot be rejected from {existing.status!r}")
        now = utc_now()
        existing.status = "rejected"
        existing.error_code = "TOOL_APPROVAL_REJECTED"
        existing.error_message = "Tool call was rejected"
        existing.updated_at = now
        existing.completed_at = now
        step = self._require_tool_step(
            run_id=existing.run_id,
            run_step_id=existing.run_step_id,
        )
        self.trace_writer.update_step_status(
            step.id,
            "canceled",
            error_code=existing.error_code,
            error_message=existing.error_message,
        )
        self.db.add(existing)
        self.db.commit()
        self.db.refresh(existing)
        self.db.refresh(step)
        return ToolExecutionClaim(record=existing, run_step=step)

    def mark_running(self, record_id: str) -> RunStepToolCall:
        """Mark the durable claim immediately before crossing the tool boundary."""

        record = self._require_record(record_id)
        if record.status == "running":
            if record.lease_owner != self.lease_owner:
                raise ConflictError("Tool-call lease owner no longer matches")
            return record
        if record.status not in {"claimed", "retrying"}:
            raise ConflictError(f"Tool call cannot start from status {record.status!r}")
        if record.lease_owner != self.lease_owner:
            raise ConflictError("Tool-call lease owner no longer matches")
        now = utc_now()
        record.status = "running"
        record.outbound_started_at = now
        record.updated_at = now
        record.lease_expires_at = now + timedelta(seconds=self.lease_seconds)
        step = self._require_tool_step(run_id=record.run_id, run_step_id=record.run_step_id)
        if step.status in {"queued", "preparing", "waiting_approval", "retrying", "paused"}:
            self.trace_writer.update_step_status(step.id, "running")
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def renew_lease(self, record_id: str) -> RunStepToolCall:
        """Extend an active claim only when this worker still owns it."""

        now = utc_now()
        result = self.db.execute(
            update(RunStepToolCall)
            .where(
                RunStepToolCall.id == record_id,
                RunStepToolCall.tenant_id == self.ctx.tenant_id,
                RunStepToolCall.workspace_id == self.ctx.workspace_id,
                RunStepToolCall.lease_owner == self.lease_owner,
                RunStepToolCall.status.in_({"claimed", "running"}),
            )
            .values(
                lease_expires_at=now + timedelta(seconds=self.lease_seconds),
                updated_at=now,
            )
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            self.db.rollback()
            raise ConflictError("Tool-call lease owner no longer matches")
        self.db.commit()
        record = self._require_record(record_id)
        self.db.refresh(record)
        return record

    async def complete(self, record_id: str, response: ToolResponse) -> RunStepToolCall:
        """Persist a terminal tool response and finish the linked RunStep."""

        record = self._require_record(record_id)
        if record.status in {"succeeded", "failed"}:
            return record
        if record.status not in {"claimed", "running"}:
            raise ConflictError(f"Tool call cannot complete from status {record.status!r}")
        if record.lease_owner != self.lease_owner:
            raise ConflictError("Tool-call lease owner no longer matches")
        if (
            record.lease_expires_at is None
            or _aware_utc(record.lease_expires_at) <= utc_now()
        ):
            raise ConflictError("Tool-call lease expired before completion")
        now = utc_now()
        record.status = "succeeded" if response.success else "failed"
        result_payload = {
            "result": _json_payload(response.result),
            "metadata": _json_payload(response.metadata),
        }
        encoded_result = json.dumps(
            result_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
        if len(encoded_result) > 8192:
            if self.storage_port is None:
                raise ValueError("Storage port is required for large tool results")
            storage_key = (
                f"tenants/{self.ctx.tenant_id}/workspaces/{self.ctx.workspace_id}/"
                f"runs/{record.run_id}/tool-calls/{record.id}/result.json"
            )
            await self.storage_port.put(
                storage_key,
                encoded_result,
                content_type="application/json",
                metadata={"run_step_id": record.run_step_id, "tool_call_id": record.tool_call_id},
            )
            artifact = self.trace_writer.create_artifact(
                run_id=record.run_id,
                step_id=record.run_step_id,
                artifact_type="json",
                storage_key=storage_key,
                mime="application/json",
                size_bytes=len(encoded_result),
                sha256=hashlib.sha256(encoded_result).hexdigest(),
                meta={"kind": "tool_result", "tool_call_id": record.tool_call_id},
            )
            record.result_artifact_id = artifact.id
            record.result_json = {
                "metadata": _json_payload(response.metadata),
                "artifact": {"id": artifact.id, "size_bytes": len(encoded_result)},
            }
        else:
            record.result_json = result_payload
        record.error_code = None if response.success else "TOOL_ERROR"
        record.error_message = response.error
        record.lease_owner = None
        record.lease_expires_at = None
        record.updated_at = now
        record.completed_at = now
        step = self._require_tool_step(run_id=record.run_id, run_step_id=record.run_step_id)
        existing_tool_metrics = dict((step.metrics_json or {}).get("tool_call") or {})
        existing_tool_metrics.update(
            {
                "tool_call_id": record.tool_call_id,
                "tool_ref": record.tool_ref,
                "attempt_count": record.attempt_count,
                "replayed": False,
            }
        )
        self.trace_writer.update_step_status(
            step.id,
            "succeeded" if response.success else "failed",
            output_summary=str(response.result)[:8192] if response.result is not None else None,
            metrics={
                "tool_call": existing_tool_metrics
            },
            error_code=record.error_code,
            error_message=record.error_message,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    async def load_cached_response(self, claim: ToolExecutionClaim) -> ToolResponse | None:
        """Resolve an inline or artifact-backed replay response."""

        if not claim.replayed:
            return None
        if claim.record.result_artifact_id is None:
            return claim.cached_response
        if self.storage_port is None:
            raise ValueError("Storage port is required to replay a large tool result")
        artifact = self.db.get(RunArtifact, claim.record.result_artifact_id)
        if (
            artifact is None
            or artifact.tenant_id != self.ctx.tenant_id
            or artifact.workspace_id != self.ctx.workspace_id
            or artifact.run_id != claim.record.run_id
            or artifact.step_id != claim.record.run_step_id
        ):
            raise ValueError("Tool result artifact scope mismatch")
        payload = json.loads((await self.storage_port.get(artifact.storage_key)).decode("utf-8"))
        return ToolResponse(
            result=payload.get("result"),
            success=claim.record.status == "succeeded",
            error=claim.record.error_message,
            metadata={
                **dict(payload.get("metadata") or {}),
                "idempotent_replay": True,
                "result_artifact_id": artifact.id,
            },
        )

    def fail(
        self,
        record_id: str,
        _error: Exception,
        *,
        error_code: str = "TOOL_EXECUTION_FAILED",
    ) -> RunStepToolCall:
        """Persist a known adapter failure without retaining sensitive details."""

        record = self._require_record(record_id)
        if record.status in {"succeeded", "failed"}:
            return record
        if record.lease_owner != self.lease_owner:
            raise ConflictError("Tool-call lease owner no longer matches")
        now = utc_now()
        record.status = "failed"
        record.result_json = {}
        record.error_code = error_code
        record.error_message = "Tool execution failed"
        record.lease_owner = None
        record.lease_expires_at = None
        record.updated_at = now
        record.completed_at = now
        step = self._require_tool_step(run_id=record.run_id, run_step_id=record.run_step_id)
        if step.status not in {"failed", "canceled", "expired"}:
            self.trace_writer.update_step_status(
                step.id,
                "failed",
                error_code=error_code,
                error_message="Tool execution failed",
            )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record
