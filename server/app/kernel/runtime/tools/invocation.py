"""Invoke one governed tool by reference, as a run of its own.

The tool invocation API and the MCP endpoint call tools directly rather than
through an agent. Each call still crosses the boundary an agent's call does:
the tool policy gateway injects secrets, checks egress, rate limits and spend,
and writes the audit record, the step and the cost. The call is recorded as a
run with ``mode="tool"``, so it is found, replayed and exported like any other.

Idempotency. The caller's key names one logical call. Sending the same key
again returns the recorded outcome instead of calling the tool twice, and a
key reused for another tool or other arguments is a conflict. Keys are scoped
to the caller: two API keys cannot collide, or read each other's outcomes.

Approval. A tool whose policy requires approval does not run on the first
call. The call is recorded as waiting, an approval request is opened, and the
caller gets the run, the approval and the key. Once someone has decided, the
same call with the same key runs the tool, or reports the rejection. Only the
arguments that were put up for approval can run: the retry must carry them
unchanged.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, replace
from typing import Any

from sqlalchemy import and_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.commons.errors import (
    ConflictError,
    ForbiddenError,
    KernelError,
    NotFoundError,
    ValidationError,
)
from app.kernel.commons.ids import generate_ulid
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.approvals.interface import ApprovalRecord, ToolApprovalPort
from app.kernel.ports.common.policy import unwrap_retry_error
from app.kernel.ports.tools.catalog import CatalogTool, ToolCatalogPort
from app.kernel.ports.tools.interface import ToolPort, ToolResponse
from app.kernel.runtime.db.models.runs import Run, RunStepToolCall
from app.kernel.runtime.runs.tool_calls import (
    RuntimeToolExecutionService,
    ToolExecutionCommand,
    canonical_request_hash,
    summarize_parameters,
    summarize_tool_payload,
)
from app.kernel.runtime.runs.writer import TraceWriter
from app.kernel.runtime.status import ApprovalStatus
from app.kernel.runtime.tools.approval import tool_approval_rule

logger = logging.getLogger(__name__)

TOOL_RUN_MODE = "tool"
TOOL_RUN_SOURCE = "gateway"
MAX_IDEMPOTENCY_KEY_LENGTH = 255
REJECTED_ERROR_CODE = "TOOL_APPROVAL_REJECTED"


@dataclass(frozen=True)
class ToolInvocation:
    """The outcome of one call, as the caller sees it."""

    run_id: str
    tool_call_id: str
    tool_ref: str
    status: str
    """``succeeded``, ``failed``, ``waiting_approval`` or ``rejected``."""
    idempotency_key: str
    result: Any = None
    error: str | None = None
    approval_id: str | None = None
    replayed: bool = False


@dataclass(frozen=True)
class _ApprovalGate:
    reason: str
    policy_ref: str | None
    risk_level: str


def _summary(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(summarize_tool_payload(value), ensure_ascii=False, default=str)[:8192]


class ToolInvocationService:
    """Invoke tools by reference on behalf of one caller."""

    def __init__(
        self,
        db: AsyncSession,
        ctx: RequestContext,
        *,
        catalog: ToolCatalogPort,
        tool_port: ToolPort,
        trace_writer: TraceWriter,
        approvals: ToolApprovalPort | None = None,
        approval_checkpoint_gateway: Any | None = None,
    ) -> None:
        self.db = db
        self.ctx = ctx
        self.catalog = catalog
        self.tool_port = tool_port
        self.trace_writer = trace_writer
        self.approvals = approvals
        self.approval_checkpoint_gateway = approval_checkpoint_gateway

    async def list_tools(self) -> list[CatalogTool]:
        """The tools this caller may invoke."""

        return [tool for tool in await self.catalog.list_tools(self.ctx) if self.ctx.may_invoke_tool(tool.ref)]

    async def get_tool(self, tool_ref: str) -> CatalogTool:
        """The tool behind ``tool_ref``, when this caller may invoke it."""

        # Refused before the lookup: a key limited to other tools learns
        # nothing about which refs exist.
        if not self.ctx.may_invoke_tool(tool_ref):
            raise ForbiddenError(
                "This API key may not invoke this tool",
                {"param": "tool_ref", "tool_ref": tool_ref, "reason": "tool_not_allowed"},
            )
        tool = await self.catalog.get_tool(self.ctx, tool_ref)
        if tool is None:
            raise NotFoundError(f"Tool not found: {tool_ref}", {"tool_ref": tool_ref})
        return tool

    async def invoke(
        self,
        tool_ref: str,
        arguments: dict[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> ToolInvocation:
        """Call ``tool_ref`` with ``arguments``, or continue the call ``idempotency_key`` names."""

        if idempotency_key is not None:
            idempotency_key = idempotency_key.strip()
            if not idempotency_key or len(idempotency_key) > MAX_IDEMPOTENCY_KEY_LENGTH:
                raise ValidationError(
                    f"An idempotency key is 1 to {MAX_IDEMPOTENCY_KEY_LENGTH} characters",
                    {"param": "idempotency_key"},
                )
        tool = await self.get_tool(tool_ref)
        caller_key = idempotency_key or f"key_{generate_ulid()}"
        stored_key = self._stored_key(caller_key)
        if idempotency_key is not None:
            record = await self._find_record(stored_key)
            if record is not None:
                return await self._continue(record, tool, arguments, caller_key)
        return await self._start(tool, arguments, caller_key, stored_key)

    async def invoke_or_continue(self, tool_ref: str, arguments: dict[str, Any]) -> ToolInvocation:
        """Call ``tool_ref``, or continue this caller's call of it that waits for approval.

        For clients that cannot carry an idempotency key, such as MCP clients
        driven by a model: the same call, sent again once its approval is
        decided, runs it or reports the rejection. A call with other arguments
        is a new call.
        """

        tool = await self.get_tool(tool_ref)
        waiting = await self._find_waiting(tool.ref, arguments)
        if waiting is not None:
            return await self._continue(waiting, tool, arguments, caller_key="")
        caller_key = f"key_{generate_ulid()}"
        return await self._start(tool, arguments, caller_key, self._stored_key(caller_key))

    def _subject(self) -> tuple[str, str]:
        if self.ctx.api_key_id:
            return "api_key", self.ctx.api_key_id
        return "user", self.ctx.user_id

    def _stored_key(self, caller_key: str) -> str:
        # The stored key travels downstream as the Idempotency-Key header of
        # HTTP tools, so it names the caller without revealing who that is.
        subject_kind, subject_id = self._subject()
        digest = hashlib.sha256(f"{subject_kind}:{subject_id}:{caller_key}".encode()).hexdigest()
        return f"invoke:{digest[:48]}"

    async def _find_record(self, stored_key: str) -> RunStepToolCall | None:
        statement = select(RunStepToolCall).where(
            and_(
                RunStepToolCall.tenant_id == self.ctx.tenant_id,
                RunStepToolCall.workspace_id == self.ctx.workspace_id,
                RunStepToolCall.idempotency_key == stored_key,
            )
        )
        return (await self.db.exec(statement)).scalars().first()

    async def _find_waiting(self, tool_ref: str, arguments: dict[str, Any]) -> RunStepToolCall | None:
        subject_kind, subject_id = self._subject()
        statement = (
            select(RunStepToolCall)
            .join(Run, Run.id == RunStepToolCall.run_id)
            .where(
                and_(
                    RunStepToolCall.tenant_id == self.ctx.tenant_id,
                    RunStepToolCall.workspace_id == self.ctx.workspace_id,
                    RunStepToolCall.tool_ref == tool_ref,
                    RunStepToolCall.request_hash == canonical_request_hash(arguments),
                    RunStepToolCall.status == "waiting_approval",
                    Run.tenant_id == self.ctx.tenant_id,
                    Run.workspace_id == self.ctx.workspace_id,
                    Run.mode == TOOL_RUN_MODE,
                    Run.subject_kind == subject_kind,
                    Run.subject_id == subject_id,
                )
            )
            .order_by(RunStepToolCall.created_at.desc())
            .limit(1)
        )
        return (await self.db.exec(statement)).scalars().first()

    def _execution_service(self, run_id: str) -> RuntimeToolExecutionService:
        return RuntimeToolExecutionService(
            db=self.db,
            ctx=self.ctx,
            trace_writer=self.trace_writer,
            lease_owner=str(self.ctx.request_id or f"tool-invoke:{run_id}"),
        )

    def _approval_gate(
        self,
        tool: CatalogTool,
        *,
        run_id: str,
        tool_call_id: str,
        arguments: dict[str, Any],
    ) -> _ApprovalGate | None:
        rule = tool_approval_rule(tool.policy)
        decision = None
        if self.approval_checkpoint_gateway is not None:
            decision = self.approval_checkpoint_gateway.evaluate(
                self.ctx,
                {
                    "action": "invoke",
                    "resource_type": "tool",
                    "resource_ref": tool.ref,
                    "risk_level": rule.risk_level,
                    "run_id": run_id,
                    "title": f"Approve tool call: {tool.ref}",
                    "details": {
                        "tool_call_id": tool_call_id,
                        "tool_ref": tool.ref,
                        "tool_type": tool.source_kind,
                        "parameters": arguments,
                    },
                },
            )
        gateway_requires = bool(getattr(decision, "requires_approval", False))
        if not rule.required and not gateway_requires:
            return None
        if gateway_requires:
            return _ApprovalGate(
                reason=str(getattr(decision, "reason", "approval_required")),
                policy_ref=getattr(decision, "policy_ref", None),
                risk_level=rule.risk_level,
            )
        return _ApprovalGate(
            reason="tool_spec_approval_required",
            policy_ref=f"tool_spec:{tool.ref}",
            risk_level=rule.risk_level,
        )

    async def _start(
        self,
        tool: CatalogTool,
        arguments: dict[str, Any],
        caller_key: str,
        stored_key: str,
    ) -> ToolInvocation:
        subject_kind, subject_id = self._subject()
        run = await self.trace_writer.create_run(
            TOOL_RUN_MODE,
            kind="tool",
            subject_kind=subject_kind,
            subject_id=subject_id,
            input_summary=f"tool={tool.ref}",
            source=TOOL_RUN_SOURCE,
        )
        await self.trace_writer.update_run_status(run.id, "running")
        await self.db.commit()
        tool_call_id = f"call_{generate_ulid()}"
        gate = self._approval_gate(tool, run_id=run.id, tool_call_id=tool_call_id, arguments=arguments)
        if gate is not None:
            return await self._wait_for_approval(
                tool, arguments, run.id, tool_call_id, caller_key, stored_key, gate
            )
        return await self._execute(
            tool,
            arguments,
            run_id=run.id,
            tool_call_id=tool_call_id,
            caller_key=caller_key,
            stored_key=stored_key,
            finish_run=True,
        )

    async def _wait_for_approval(
        self,
        tool: CatalogTool,
        arguments: dict[str, Any],
        run_id: str,
        tool_call_id: str,
        caller_key: str,
        stored_key: str,
        gate: _ApprovalGate,
    ) -> ToolInvocation:
        if self.approvals is None:
            await self._fail_run(run_id, "APPROVAL_UNAVAILABLE", "This tool requires approval")
            raise KernelError(
                "SERVICE_UNAVAILABLE",
                "This tool requires approval, and approvals are not available here",
                {"tool_ref": tool.ref},
            )
        await self._execution_service(run_id).prepare_waiting_approval(
            ToolExecutionCommand(
                run_id=run_id,
                tool_call_id=tool_call_id,
                tool_ref=tool.ref,
                arguments=arguments,
                idempotency_key=stored_key,
                created_by=self.ctx.user_id,
            )
        )
        await self.trace_writer.update_run_status(run_id, "waiting_approval")
        await self.db.commit()
        try:
            approval_id = await self.approvals.open(
                self.ctx,
                ApprovalRecord(
                    run_id=run_id,
                    task_id=None,
                    thread_id=None,
                    agent_id=None,
                    title=f"Approve tool call: {tool.ref}",
                    policy_ref=gate.policy_ref,
                    tool_call_id=tool_call_id,
                    details={
                        "tool_ref": tool.ref,
                        "tool_type": tool.source_kind,
                        "parameters": summarize_parameters(arguments),
                        "reason": gate.reason,
                        "risk_level": gate.risk_level,
                        "source": "tool_invocation",
                    },
                ),
            )
        except Exception:
            # Nobody could ever decide a request that was not written; the
            # call must not wait on it.
            logger.warning("Failed to open an approval for %s", tool.ref, exc_info=True)
            await self.db.rollback()
            await self._fail_run(run_id, "APPROVAL_UNAVAILABLE", "The approval request could not be opened")
            raise
        return ToolInvocation(
            run_id=run_id,
            tool_call_id=tool_call_id,
            tool_ref=tool.ref,
            status="waiting_approval",
            idempotency_key=caller_key,
            approval_id=approval_id,
        )

    async def _continue(
        self,
        record: RunStepToolCall,
        tool: CatalogTool,
        arguments: dict[str, Any],
        caller_key: str,
    ) -> ToolInvocation:
        if record.tool_ref != tool.ref:
            raise ConflictError(
                "This idempotency key was used for another tool",
                {"param": "idempotency_key", "tool_ref": record.tool_ref},
            )
        if record.status == "rejected":
            return self._rejected(record, caller_key)
        if record.status != "waiting_approval":
            # A recorded outcome replays; a call still in flight is refused as
            # already claimed; other arguments are refused as a conflict.
            return await self._execute(
                tool,
                arguments,
                run_id=record.run_id,
                tool_call_id=record.tool_call_id,
                caller_key=caller_key,
                stored_key=record.idempotency_key,
                run_step_id=record.run_step_id,
                finish_run=False,
            )

        if canonical_request_hash(arguments) != record.request_hash:
            raise ConflictError(
                "This idempotency key was used with other arguments",
                {"param": "idempotency_key"},
            )
        decision = (
            await self.approvals.decision_for(
                self.ctx, run_id=record.run_id, tool_call_id=record.tool_call_id
            )
            if self.approvals is not None
            else None
        )
        if decision is None or decision.status == ApprovalStatus.PENDING.value:
            return ToolInvocation(
                run_id=record.run_id,
                tool_call_id=record.tool_call_id,
                tool_ref=record.tool_ref,
                status="waiting_approval",
                idempotency_key=caller_key,
                approval_id=decision.approval_id if decision else None,
            )
        if decision.status == ApprovalStatus.APPROVED.value:
            await self.trace_writer.update_run_status(record.run_id, "running")
            await self.db.commit()
            invocation = await self._execute(
                tool,
                arguments,
                run_id=record.run_id,
                tool_call_id=record.tool_call_id,
                caller_key=caller_key,
                stored_key=record.idempotency_key,
                run_step_id=record.run_step_id,
                resume_approval=True,
                finish_run=True,
            )
            return replace(invocation, approval_id=decision.approval_id)

        note = (decision.resolution_note or "").strip() or "Tool call was rejected"
        await self._execution_service(record.run_id).reject_approval(
            ToolExecutionCommand(
                run_id=record.run_id,
                run_step_id=record.run_step_id,
                tool_call_id=record.tool_call_id,
                tool_ref=record.tool_ref,
                arguments=arguments,
                idempotency_key=record.idempotency_key,
                created_by=self.ctx.user_id,
            )
        )
        await self.trace_writer.update_run_status(
            record.run_id,
            "canceled",
            error_code=REJECTED_ERROR_CODE,
            error_message=note[:2000],
        )
        await self.db.commit()
        return replace(self._rejected(record, caller_key), approval_id=decision.approval_id)

    def _rejected(self, record: RunStepToolCall, caller_key: str) -> ToolInvocation:
        return ToolInvocation(
            run_id=record.run_id,
            tool_call_id=record.tool_call_id,
            tool_ref=record.tool_ref,
            status="rejected",
            idempotency_key=caller_key,
            error="Tool call was rejected",
        )

    async def _execute(
        self,
        tool: CatalogTool,
        arguments: dict[str, Any],
        *,
        run_id: str,
        tool_call_id: str,
        caller_key: str,
        stored_key: str,
        finish_run: bool,
        run_step_id: str | None = None,
        resume_approval: bool = False,
    ) -> ToolInvocation:
        try:
            response: ToolResponse = await self.tool_port.invoke(
                tool_ref=tool.ref,
                parameters=arguments,
                ctx=self.ctx,
                run_id=run_id,
                tool_call_id=tool_call_id,
                idempotency_key=stored_key,
                run_step_id=run_step_id,
                resume_approval=resume_approval,
                strict_registry=True,
            )
        except Exception as exc:
            # The gateway retries through tenacity, which wraps what the tool
            # raised; the caller is owed the refusal itself (400, 403, ...).
            root = unwrap_retry_error(exc)
            if finish_run:
                await self.db.rollback()
                await self._fail_run(
                    run_id,
                    getattr(root, "code", None) or "TOOL_INVOCATION_FAILED",
                    str(root),
                )
            if root is not exc:
                raise root from exc
            raise
        replayed = bool((response.metadata or {}).get("idempotent_replay"))
        status = "succeeded" if response.success else "failed"
        if finish_run and not replayed:
            await self.trace_writer.update_run_status(
                run_id,
                status,
                output_summary=_summary(response.result) if response.success else None,
                error_code=None if response.success else "TOOL_ERROR",
                error_message=None if response.success else (response.error or "")[:2000] or None,
            )
            await self.db.commit()
        return ToolInvocation(
            run_id=run_id,
            tool_call_id=tool_call_id,
            tool_ref=tool.ref,
            status=status,
            idempotency_key=caller_key,
            result=response.result if response.success else None,
            error=None if response.success else response.error,
            replayed=replayed,
        )

    async def _fail_run(self, run_id: str, error_code: str, message: str) -> None:
        try:
            await self.trace_writer.update_run_status(
                run_id, "failed", error_code=error_code, error_message=message[:2000]
            )
            await self.db.commit()
        except Exception:
            logger.warning("Failed to close tool run %s", run_id, exc_info=True)
            await self.db.rollback()
