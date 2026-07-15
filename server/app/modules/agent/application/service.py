""" service

Agent domain service.
"""

import time
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.kernel.commons.errors import KernelError, ValidationError
from app.kernel.commons.ids import generate_run_id
from app.kernel.contracts.context import RequestContext
from app.kernel.identity.guard import workspace_guard
from app.kernel.ports.common.rate_limiter import RateLimiter
from app.kernel.ports.llm.interface import ChatMessage, LLMPort, ToolDefinition
from app.kernel.ports.tools.interface import ToolPort
from app.kernel.runtime.db.models.runs import Run
from app.kernel.runtime.responses.service import ResponseService
from app.kernel.runtime.runs.writer import TraceWriter
from app.kernel.runtime.tools.resolver import ToolResolver
from app.modules.agent.application.contracts import (
    AgentCapabilityCatalogPort,
    EmptyAgentCapabilityCatalog,
)
from app.modules.agent.application.schemas import AgentRuntimeRequest
from app.modules.agent.runtime.emitter import EventEmitter, noop_emitter
from app.modules.agent.runtime.executor import AgentExecutor
from app.modules.agent.runtime.planner import AgentPlanner
from app.modules.agent.runtime.verifier import AgentVerifier
from app.modules.memory.application.service import MemoryService
from app.settings.settings import settings


class AgentService:
    """Agent service for plan-execute-verify."""

    def _ensure_run_active(self, run_id: str) -> None:
        if not self.trace_writer:
            return
        run_status = self.trace_writer.db.execute(
            select(Run.status).where(
                Run.id == run_id,
                Run.tenant_id == self.ctx.tenant_id,
                Run.workspace_id == self.ctx.workspace_id,
            )
        ).scalar_one_or_none()
        if run_status == "canceled":
            raise KernelError(
                "AGENT_RUN_CANCELED",
                f"Agent run was canceled: {run_id}",
                {"run_id": run_id},
            )

    def __init__(
        self,
        db: Session,
        ctx: RequestContext,
        llm_port: LLMPort,
        tool_port: ToolPort,
        tool_resolver: ToolResolver | None = None,
        memory_service: MemoryService | None = None,
        response_service: ResponseService | None = None,
        trace_writer: TraceWriter | None = None,
        rate_limiter: RateLimiter | None = None,
        workflow_executor: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]] | None = None,
        capability_catalog: AgentCapabilityCatalogPort | None = None,
    ):
        self.db = db
        self.ctx = ctx
        self.llm_port = llm_port
        self.tool_port = tool_port
        self.tool_resolver = tool_resolver
        self.memory_service = memory_service
        self.response_service = response_service
        self.trace_writer = trace_writer
        self.rate_limiter = rate_limiter or RateLimiter()
        self.workflow_executor = workflow_executor
        self.capability_catalog = capability_catalog or EmptyAgentCapabilityCatalog()
        self.planner = AgentPlanner(llm_port)
        self.executor = AgentExecutor(tool_port)
        self.verifier = AgentVerifier(llm_port)

    def _resolve_agent_trace_subject(self) -> tuple[str, str]:
        return self.ctx.workspace_id, "agent-runtime:v1"

    @staticmethod
    def _attachment_context(metadata: dict[str, Any] | None) -> str:
        attachments = (metadata or {}).get("attachments")
        if not isinstance(attachments, list):
            return ""
        blocks: list[str] = []
        for index, attachment in enumerate(attachments, start=1):
            if not isinstance(attachment, dict):
                continue
            name = attachment.get("name") or attachment.get("filename") or f"attachment-{index}"
            content = attachment.get("content")
            lines: list[str] = []
            if isinstance(content, str):
                lines.append(content)
            elif isinstance(content, list):
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    text = part.get("text") or part.get("content")
                    if isinstance(text, str) and text.strip():
                        lines.append(text)
            if lines:
                blocks.append(f"[{name}]\n" + "\n".join(lines))
        if not blocks:
            return ""
        return "Attached context:\n" + "\n\n".join(blocks)

    @classmethod
    def _message_content_with_attachments(cls, content: str, metadata: dict[str, Any] | None) -> str:
        attachment_context = cls._attachment_context(metadata)
        if not attachment_context:
            return content
        return f"{content}\n\n{attachment_context}" if content else attachment_context

    @workspace_guard("write")
    async def run(
        self,
        data: AgentRuntimeRequest,
        *,
        existing_run_id: str | None = None,
        response_id: str | None = None,
        event_emitter: EventEmitter | None = None,
    ) -> dict[str, Any]:
        """Run agent loop."""
        if not isinstance(data, AgentRuntimeRequest):
            raise TypeError("AgentService.run requires AgentRuntimeRequest")
        emit = event_emitter or noop_emitter
        run_id = existing_run_id or generate_run_id()
        if settings.agent_rate_limit_per_minute:
            await self.rate_limiter.check_rate_limit(
                key=f"agent:run:{self.ctx.tenant_id}:{self.ctx.workspace_id}:{self.ctx.user_id or 'anonymous'}",
                limit=settings.agent_rate_limit_per_minute,
                window_seconds=60,
            )
        if self.trace_writer:
            if existing_run_id:
                self._ensure_run_active(run_id)
                self.trace_writer.update_run_status(run_id, "running")
            else:
                subject_id, subject_version_id = self._resolve_agent_trace_subject()
                run = self.trace_writer.create_run(
                    mode="agent",
                    subject_kind="agent",
                    subject_id=subject_id,
                    subject_version_id=subject_version_id,
                    input_summary=data.messages[-1].content[:8192],
                    run_id=run_id,
                    request_id=data.request_id,
                )
                run_id = run.id
                self.trace_writer.update_run_status(run_id, "running")

        messages = [
            ChatMessage(
                role=m.role,
                content=self._message_content_with_attachments(m.content, m.metadata),
            )
            for m in data.messages
        ]
        messages = self._apply_context_window(
            messages,
            max_messages=data.context_window_messages,
            max_chars=data.context_window_chars,
        )
        memory_context = None

        if self.memory_service and (data.memory_strategy or data.memory_query or data.memory_top_k):
            query_text = data.memory_query or data.messages[-1].content
            try:
                results = await self.memory_service.query_memory(
                    self._build_memory_query(query_text=query_text, top_k=data.memory_top_k or 5),
                    run_id=run_id,
                )
                memory_lines = []
                for item in results:
                    summary = item.memory.content_summary or str(item.memory.content)
                    memory_lines.append(f"- {summary}")
                if memory_lines:
                    memory_context = "\n".join(memory_lines)
            except Exception:
                memory_context = None

        if memory_context and data.memory_strategy in ("system_message", "user_message"):
            role = "system" if data.memory_strategy == "system_message" else "user"
            messages = [ChatMessage(role=role, content=f"Memory context:\n{memory_context}")] + messages
            memory_context = None

        # RAG retrieval from knowledge bases
        rag_context = None
        rag_citations: list[dict[str, Any]] = []
        if data.knowledge_refs:
            query_text = data.messages[-1].content
            rag_context, rag_citations = await self._retrieve_rag_context(
                knowledge_refs=data.knowledge_refs,
                query=query_text,
                top_k=data.rag_top_k,
                run_id=run_id,
            )

        if rag_context and data.rag_strategy == "system_message":
            messages = [ChatMessage(role="system", content=f"Retrieved context:\n{rag_context}")] + messages
            rag_context = None

        model = data.model_ref
        iterations = 0
        final_response = ""
        tokens_prompt = 0
        tokens_completion = 0
        finish_reason = None
        tool_calls = 0
        tool_call_details: list[dict[str, Any]] = []
        llm_calls = 0
        failures = 0
        budget_exceeded = False
        budget_reason = None
        started_at = time.monotonic()
        cost_total = 0.0

        def set_budget(reason: str) -> None:
            nonlocal budget_exceeded, budget_reason, final_response, finish_reason
            budget_exceeded = True
            budget_reason = reason
            finish_reason = reason
            if not final_response:
                final_response = f"Agent stopped: {reason}."

        def check_runtime_budget() -> bool:
            if data.max_runtime_seconds is None:
                return False
            elapsed = time.monotonic() - started_at
            if elapsed >= data.max_runtime_seconds:
                set_budget("time_budget_exceeded")
                return True
            return False

        def check_cost_budget() -> bool:
            nonlocal cost_total
            if data.max_cost is None:
                return False
            cost_total = self._get_cost_total(run_id, data.cost_currency)
            if cost_total >= data.max_cost:
                set_budget("cost_budget_exceeded")
                return True
            return False

        def handle_failure(message: str, reason: str) -> bool:
            nonlocal failures, final_response, finish_reason
            if failures <= data.max_failures:
                return False
            if data.failure_strategy == "continue":
                failures = 0
                return False
            if data.failure_strategy == "abort":
                raise ValidationError(message)
            final_response = message
            finish_reason = reason
            return True

        def build_tool_metrics(
            *,
            tool_ref: str,
            parameters: dict[str, Any],
            status: str,
            tool_type: str = "builtin",
            result: dict[str, Any] | None = None,
            metadata: dict[str, Any] | None = None,
            error_code: str | None = None,
            error_message: str | None = None,
        ) -> dict[str, Any]:
            return {
                "tool_call": {
                    "tool_name": tool_ref,
                    "tool_ref": tool_ref,
                    "tool_type": tool_type,
                    "status": status,
                    "arguments": parameters or {},
                    "result": result or {},
                    "metadata": metadata or {},
                    "error_code": error_code,
                    "error_message": error_message,
                }
            }

        # Resolve tool definitions for function calling
        resolved_tool_refs = list(data.tool_refs or [])
        tool_definitions = None
        if self.tool_resolver and resolved_tool_refs:
            tool_definitions = await self.tool_resolver.resolve(resolved_tool_refs, self.ctx)
        if data.workflow_refs:
            workflow_definitions = [
                ToolDefinition(
                    name=ref,
                    description=f"Execute bound workflow {ref}",
                    parameters=self._workflow_tool_parameters(ref),
                )
                for ref in data.workflow_refs
            ]
            tool_definitions = [*(tool_definitions or []), *workflow_definitions]

        try:
            await emit("agent.run.started", {"run_id": run_id})
            while iterations < data.max_iterations:
                self._ensure_run_active(run_id)
                if check_runtime_budget():
                    break
                if data.max_llm_calls is not None and llm_calls >= data.max_llm_calls:
                    set_budget("llm_budget_exceeded")
                    break
                iterations += 1
                plan_step_id = None
                if self.trace_writer:
                    step = self.trace_writer.create_step(
                        run_id=run_id,
                        step_type="agent_plan",
                        input_summary=f"iteration={iterations}",
                    )
                    plan_step_id = step.id
                    self.trace_writer.update_step_status(plan_step_id, "running")

                await emit("agent.plan.started", {"iteration": iterations})
                llm_cost_count_before = self._count_llm_token_cost_entries(run_id)
                try:
                    plan = await self.planner.plan(
                        messages=messages,
                        tool_definitions=tool_definitions,
                        model=model,
                        temperature=data.temperature,
                        run_id=run_id,
                        memory_context=memory_context,
                        rag_context=rag_context,
                    )
                except Exception as exc:
                    if self.trace_writer and plan_step_id:
                        self.trace_writer.update_step_status(
                            plan_step_id,
                            "failed",
                            error_message=str(exc),
                        )
                    raise
                llm_calls += 1
                self._ensure_run_active(run_id)
                tokens_prompt += plan.tokens_prompt
                tokens_completion += plan.tokens_completion
                finish_reason = plan.finish_reason or finish_reason
                await emit("agent.plan.succeeded", {"action": plan.action, "iteration": iterations})
                if (
                    self.trace_writer
                    and plan_step_id
                    and (plan.tokens_prompt or plan.tokens_completion)
                    and self._count_llm_token_cost_entries(run_id) == llm_cost_count_before
                ):
                    self.trace_writer.record_cost(
                        run_id=run_id,
                        step_id=plan_step_id,
                        unit="tokens",
                        quantity=(plan.tokens_prompt or 0) + (plan.tokens_completion or 0),
                        currency=data.cost_currency,
                        amount=0,
                        model_ref=model,
                        prompt_tokens=plan.tokens_prompt,
                        completion_tokens=plan.tokens_completion,
                        total_tokens=(plan.tokens_prompt or 0) + (plan.tokens_completion or 0),
                    )
                if check_cost_budget():
                    break

                if self.trace_writer and plan_step_id:
                    self.trace_writer.update_step_status(
                        plan_step_id,
                        "succeeded",
                        output_summary=f"action={plan.action}",
                        metrics={
                            "tokens_prompt": plan.tokens_prompt,
                            "tokens_completion": plan.tokens_completion,
                        },
                    )

                if data.max_tokens_total is not None:
                    total_tokens = tokens_prompt + tokens_completion
                    if total_tokens >= data.max_tokens_total:
                        set_budget("token_budget_exceeded")
                        break

                if plan.action == "tool":
                    if not plan.tool_calls:
                        failures += 1
                        messages.append(
                            ChatMessage(role="assistant", content="Planner error: no tool calls returned.")
                        )
                        if handle_failure("Planner failed to select tool.", "planner_failed"):
                            break
                        continue

                    if tool_calls >= data.max_tool_calls:
                        set_budget("tool_budget_exceeded")
                        break

                    # Append assistant message with tool_calls for LLM protocol
                    messages.append(ChatMessage(
                        role="assistant",
                        content=None,
                        tool_calls=plan.tool_calls,
                    ))

                    tool_failed_break = False
                    for tc in plan.tool_calls:
                        self._ensure_run_active(run_id)
                        allowed_refs = [*resolved_tool_refs, *(data.workflow_refs or [])]
                        if allowed_refs and tc.name not in allowed_refs:
                            raise ValidationError(f"Tool not allowed: {tc.name}")
                        is_workflow_call = tc.name in (data.workflow_refs or [])
                        tool_type = "workflow" if is_workflow_call else "builtin"
                        tool_arguments = (
                            self._workflow_arguments_with_defaults(tc.arguments or {}, data)
                            if is_workflow_call
                            else (tc.arguments or {})
                        )

                        tool_step_id = None
                        if self.trace_writer:
                            step = self.trace_writer.create_step(
                                run_id=run_id,
                                step_type="tool",
                                input_summary=f"tool_ref={tc.name}",
                            )
                            tool_step_id = step.id
                            self.trace_writer.update_step_status(tool_step_id, "running")

                        tool_calls += 1
                        await emit("agent.tool.started", {"tool_ref": tc.name, "tool_call_id": tc.id})

                        if self.trace_writer and tool_step_id:
                            self.trace_writer.update_step_metrics(
                                tool_step_id,
                                build_tool_metrics(
                                    tool_ref=tc.name,
                                    parameters=tool_arguments,
                                    status="started",
                                    tool_type=tool_type,
                                    metadata={"source": "agent.tool", "iteration": iterations},
                                ),
                            )
                        if self.response_service and response_id:
                            response = self.response_service.get_response(response_id)
                            self.response_service.append_event(
                                response=response,
                                event_type="tool.call.requested",
                                payload={
                                    "response_id": response_id,
                                    "run_id": run_id,
                                    "tool_call_id": tc.id,
                                    "tool_name": tc.name,
                                    "tool_type": tool_type,
                                    "step_id": tool_step_id,
                                    "status": "requested",
                                    "arguments": tool_arguments,
                                },
                                source="agent",
                            )
                            self.response_service.append_event(
                                response=response,
                                event_type="tool.call.started",
                                payload={
                                    "response_id": response_id,
                                    "run_id": run_id,
                                    "tool_call_id": tc.id,
                                    "tool_name": tc.name,
                                    "tool_type": tool_type,
                                    "step_id": tool_step_id,
                                    "status": "started",
                                },
                                source="agent",
                            )
                        try:
                            if is_workflow_call:
                                if not self.workflow_executor:
                                    raise ValidationError(f"Workflow execution is not configured: {tc.name}")
                                workflow_result = await self.workflow_executor(tc.name, tool_arguments)
                                workflow_run_id = workflow_result.get("run_id")
                                tool_response = type(
                                    "WorkflowToolResponse",
                                    (),
                                    {
                                        "success": True,
                                        "result": {
                                            "workflow_ref": tc.name,
                                            "workflow_run_id": workflow_run_id,
                                            "output": workflow_result.get("output"),
                                        },
                                        "error": None,
                                        "metadata": {
                                            "source": "agent.workflow",
                                            "workflow_ref": tc.name,
                                            "workflow_run_id": workflow_run_id,
                                        },
                                    },
                                )()
                            else:
                                tool_response = await self.executor.execute_tool(
                                    tool_ref=tc.name,
                                    parameters=tool_arguments,
                                    ctx=self.ctx,
                                    run_id=run_id,
                                )
                        except Exception as exc:
                            if self.trace_writer and tool_step_id:
                                self.trace_writer.update_step_status(
                                    tool_step_id,
                                    "failed",
                                    metrics=build_tool_metrics(
                                        tool_ref=tc.name,
                                        parameters=tool_arguments,
                                        status="failed",
                                        tool_type=tool_type,
                                        metadata={"source": "agent.tool", "iteration": iterations},
                                        error_code="tool_execution_failed",
                                        error_message=str(exc),
                                    ),
                                    error_message=str(exc),
                                )
                            if self.response_service and response_id:
                                response = self.response_service.get_response(response_id)
                                self.response_service.append_event(
                                    response=response,
                                    event_type="tool.call.failed",
                                    payload={
                                        "response_id": response_id,
                                        "run_id": run_id,
                                        "tool_call_id": tc.id,
                                        "tool_name": tc.name,
                                        "tool_type": tool_type,
                                        "step_id": tool_step_id,
                                        "status": "failed",
                                        "error": {"code": "tool_execution_failed", "message": str(exc)},
                                    },
                                    source="agent",
                                )
                            raise
                        tool_content = (
                            str(tool_response.result)
                            if tool_response.success
                            else f"ERROR: {tool_response.error}"
                        )
                        messages.append(ChatMessage(
                            role="tool",
                            content=tool_content,
                            tool_call_id=tc.id,
                            name=tc.name,
                        ))
                        response_metadata = tool_response.metadata or {}
                        effective_tool_type = str(response_metadata.get("source_kind") or tool_type)
                        await emit(
                            "agent.tool.succeeded",
                            {
                                "tool_ref": tc.name,
                                "tool_type": effective_tool_type,
                                "tool_call_id": tc.id,
                                "success": tool_response.success,
                                "result": {"result": tool_response.result} if tool_response.success else {},
                                "metadata": response_metadata,
                                "error": None if tool_response.success else {
                                    "code": "tool_execution_failed",
                                    "message": tool_response.error,
                                },
                            },
                        )
                        tool_call_details.append(
                            {
                                "tool_call_id": tc.id,
                                "tool_name": tc.name,
                                "tool_type": effective_tool_type,
                                "status": "completed" if tool_response.success else "failed",
                                "arguments_json": tc.arguments or {},
                                "result_json": {"result": tool_response.result} if tool_response.success else {},
                                "metadata_json": response_metadata,
                                "error": None if tool_response.success else {
                                    "code": "tool_execution_failed",
                                    "message": tool_response.error,
                                },
                            }
                        )

                        if self.trace_writer and tool_step_id:
                            status = "succeeded" if tool_response.success else "failed"
                            self.trace_writer.update_step_status(
                                tool_step_id,
                                status,
                                output_summary=tool_content[:8192],
                                metrics={
                                    **response_metadata,
                                    **build_tool_metrics(
                                        tool_ref=tc.name,
                                        parameters=tc.arguments,
                                        status="completed" if tool_response.success else "failed",
                                        tool_type=effective_tool_type,
                                        result={"result": tool_response.result} if tool_response.success else {},
                                        metadata={"source": "agent.tool", "iteration": iterations, **response_metadata},
                                        error_code=None if tool_response.success else "tool_execution_failed",
                                        error_message=None if tool_response.success else tool_response.error,
                                    ),
                                },
                                error_message=None if tool_response.success else tool_response.error,
                            )
                        if self.response_service and response_id:
                            response = self.response_service.get_response(response_id)
                            self.response_service.append_event(
                                response=response,
                                event_type="tool.call.completed" if tool_response.success else "tool.call.failed",
                                payload={
                                    "response_id": response_id,
                                    "run_id": run_id,
                                    "tool_call_id": tc.id,
                                    "tool_name": tc.name,
                                    "tool_type": effective_tool_type,
                                    "step_id": tool_step_id,
                                    "status": "completed" if tool_response.success else "failed",
                                    "result": {"result": tool_response.result} if tool_response.success else {},
                                    "metadata": response_metadata,
                                    "error": None if tool_response.success else {
                                        "code": "tool_execution_failed",
                                        "message": tool_response.error,
                                    },
                                },
                                source="agent",
                            )

                        if not tool_response.success:
                            failures += 1
                            if handle_failure(
                                f"Tool failed after {failures} attempts: {tool_response.error}",
                                "tool_failed",
                            ):
                                tool_failed_break = True
                                break

                    if tool_failed_break:
                        break
                    if check_cost_budget():
                        break
                    continue

                if plan.action == "respond":
                    final_response = str(plan.response or "")
                    await emit("agent.response.succeeded", {"output": final_response})
                    break

                failures += 1
                messages.append(
                    ChatMessage(role="assistant", content="Planner returned unknown action.")
                )
                if handle_failure("Agent returned unknown action.", "planner_failed"):
                    break

            if not final_response:
                final_response = "Agent reached max iterations."
                finish_reason = finish_reason or "max_iterations"

            if data.verify and not budget_exceeded and not check_runtime_budget():
                self._ensure_run_active(run_id)
                if data.max_llm_calls is not None and llm_calls >= data.max_llm_calls:
                    set_budget("llm_budget_exceeded")
                else:
                    verify_step_id = None
                    if self.trace_writer:
                        step = self.trace_writer.create_step(
                            run_id=run_id,
                            step_type="other",
                            input_summary="verify_response",
                        )
                        verify_step_id = step.id
                        self.trace_writer.update_step_status(verify_step_id, "running")

                    try:
                        llm_cost_count_before = self._count_llm_token_cost_entries(run_id)
                        verify_result = await self.verifier.verify(
                            messages,
                            final_response,
                            model=model,
                            run_id=run_id,
                        )
                    except Exception as exc:
                        if self.trace_writer and verify_step_id:
                            self.trace_writer.update_step_status(
                                verify_step_id,
                                "failed",
                                error_message=str(exc),
                            )
                        raise
                    llm_calls += 1
                    tokens_prompt += verify_result.tokens_prompt
                    tokens_completion += verify_result.tokens_completion
                    finish_reason = verify_result.finish_reason or finish_reason
                    if (
                        self.trace_writer
                        and verify_step_id
                        and (verify_result.tokens_prompt or verify_result.tokens_completion)
                        and self._count_llm_token_cost_entries(run_id) == llm_cost_count_before
                    ):
                        self.trace_writer.record_cost(
                            run_id=run_id,
                            step_id=verify_step_id,
                            unit="tokens",
                            quantity=(verify_result.tokens_prompt or 0) + (verify_result.tokens_completion or 0),
                            currency=data.cost_currency,
                            amount=0,
                            model_ref=model,
                            prompt_tokens=verify_result.tokens_prompt,
                            completion_tokens=verify_result.tokens_completion,
                            total_tokens=(verify_result.tokens_prompt or 0) + (verify_result.tokens_completion or 0),
                        )
                    check_cost_budget()

                    if data.max_tokens_total is not None:
                        total_tokens = tokens_prompt + tokens_completion
                        if total_tokens >= data.max_tokens_total:
                            set_budget("token_budget_exceeded")

                    if self.trace_writer and verify_step_id:
                        status = "succeeded" if verify_result.ok else "failed"
                        self.trace_writer.update_step_status(
                            verify_step_id,
                            status,
                            output_summary="ok" if verify_result.ok else "not_ok",
                            metrics={
                                "tokens_prompt": verify_result.tokens_prompt,
                                "tokens_completion": verify_result.tokens_completion,
                            },
                            error_message=None if verify_result.ok else verify_result.reason,
                        )

                    if not verify_result.ok:
                        reason = verify_result.reason
                        if reason:
                            final_response = f"Agent verification failed: {reason}"
                        else:
                            final_response = "Agent verification failed."
                        finish_reason = "verification_failed"

            self._ensure_run_active(run_id)
            await emit("agent.run.succeeded", {"run_id": run_id, "status": "succeeded"})
            if self.trace_writer:
                self.trace_writer.update_run_status(
                    run_id,
                    "succeeded",
                    output_summary=final_response[:8192],
                )
        except Exception as exc:
            canceled = isinstance(exc, KernelError) and exc.code == "AGENT_RUN_CANCELED"
            if canceled:
                await emit("agent.run.canceled", {"run_id": run_id, "status": "canceled"})
            elif self.trace_writer:
                self.trace_writer.update_run_status(
                    run_id,
                    "failed",
                    output_summary=str(exc)[:8192],
                )
            raise

        return {
            "run_id": run_id,
            "request_id": data.request_id,
            "output": final_response,
            "model": model,
            "iterations": iterations,
            "tokens_prompt": tokens_prompt,
            "tokens_completion": tokens_completion,
            "finish_reason": finish_reason,
            "tool_calls": tool_calls,
            "tool_call_details": tool_call_details,
            "llm_calls": llm_calls,
            "failures": failures,
            "budget_exceeded": budget_exceeded,
            "budget_reason": budget_reason,
            "cost_total": cost_total,
            "citations": rag_citations,
        }

    def _get_cost_total(self, run_id: str, currency: str) -> float:
        """Get total cost for a run."""
        from sqlalchemy import and_, func

        from app.kernel.runtime.db.models.runs import RunCostEntry

        query = select(func.coalesce(func.sum(RunCostEntry.amount), 0)).where(
            and_(
                RunCostEntry.run_id == run_id,
                RunCostEntry.tenant_id == self.ctx.tenant_id,
                RunCostEntry.workspace_id == self.ctx.workspace_id,
                RunCostEntry.currency == currency,
            )
        )
        result = self.db.exec(query).one()
        value = self._scalar_value(result)
        return float(value or 0)

    def _count_llm_token_cost_entries(self, run_id: str) -> int:
        """Count LLM token cost entries already written for this run."""
        if not self.trace_writer:
            return 0
        from sqlalchemy import and_, func, select

        from app.kernel.runtime.db.models.runs import RunCostEntry

        query = select(func.count(RunCostEntry.id)).where(
            and_(
                RunCostEntry.run_id == run_id,
                RunCostEntry.tenant_id == self.ctx.tenant_id,
                RunCostEntry.workspace_id == self.ctx.workspace_id,
                RunCostEntry.unit == "tokens",
                RunCostEntry.model_ref.is_not(None),
            )
        )
        result = self.db.exec(query).one()
        value = self._scalar_value(result)
        return int(value or 0)

    @staticmethod
    def _scalar_value(result: Any) -> Any:
        """Extract a scalar from SQLModel/SQLAlchemy scalar, tuple, or Row results."""
        if isinstance(result, list | tuple):
            return result[0]
        try:
            return result[0]
        except Exception:
            return result

    def _workflow_tool_parameters(self, workflow_ref: str) -> dict[str, Any]:
        return self.capability_catalog.workflow_input_schema(workflow_ref)

    def _workflow_arguments_with_defaults(
        self,
        arguments: dict[str, Any],
        data: AgentRuntimeRequest,
    ) -> dict[str, Any]:
        merged = dict(arguments or {})
        merged.setdefault("model_ref", data.model_ref)
        if data.knowledge_refs:
            defaults = self.capability_catalog.knowledge_runtime_defaults(
                data.knowledge_refs[0]
            )
            for key, value in defaults.items():
                merged.setdefault(key, value)
        return merged

    async def _retrieve_rag_context(
        self,
        knowledge_refs: list[str],
        query: str,
        top_k: int = 5,
        run_id: str | None = None,
    ) -> tuple[str | None, list[dict[str, Any]]]:
        """Retrieve context from knowledge bases for RAG injection."""
        from app.modules.knowledge.application.tools import knowledge_query

        chunks: list[str] = []
        citations: list[dict[str, Any]] = []
        for ref in knowledge_refs:
            # knowledge_refs are in format "knowledge:kb_id" or just "kb_id"
            kb_id = ref.split(":")[-1] if ":" in ref else ref
            step_id = None
            if self.trace_writer and run_id:
                step = self.trace_writer.create_step(
                    run_id=run_id,
                    step_type="retrieval",
                    step_id=f"rag:{kb_id}",
                    node_id=kb_id,
                    input_summary=query,
                )
                step_id = step.id
                self.trace_writer.update_step_status(step_id, "running")
            try:
                response = await knowledge_query(
                    knowledge_id=kb_id,
                    query=query,
                    top_k=top_k,
                    ctx={
                        "tenant_id": self.ctx.tenant_id,
                        "workspace_id": self.ctx.workspace_id,
                        "user_id": self.ctx.user_id,
                        "tenant_role": self.ctx.tenant_role,
                        "workspace_role": self.ctx.workspace_role,
                    },
                )
                results = response.get("results") or []
                response_citations = response.get("citations") or []
                score_values = [
                    float(result["score"])
                    for result in results
                    if isinstance(result, dict)
                    and isinstance(result.get("score"), int | float)
                    and not isinstance(result.get("score"), bool)
                ]
                for result in response.get("results") or []:
                    text = result.get("text") or result.get("content") or ""
                    if text:
                        chunks.append(text)
                for citation in response_citations:
                    if isinstance(citation, dict):
                        citations.append({**citation, "knowledge_id": citation.get("knowledge_id") or kb_id})
                if self.trace_writer and step_id:
                    self.trace_writer.update_step_status(
                        step_id,
                        "succeeded",
                        output_summary=f"{len(results)} result(s), {len(response_citations)} citation(s)",
                        metrics={
                            "knowledge_id": kb_id,
                            "query": query,
                            "top_k": top_k,
                            "result_count": len(results),
                            "citation_count": len(response_citations),
                            "avg_score": (sum(score_values) / len(score_values)) if score_values else None,
                        },
                    )
            except Exception:
                if self.trace_writer and step_id:
                    self.trace_writer.update_step_status(
                        step_id,
                        "failed",
                        output_summary="RAG retrieval failed",
                        metrics={
                            "knowledge_id": kb_id,
                            "query": query,
                            "top_k": top_k,
                            "result_count": 0,
                            "citation_count": 0,
                        },
                        error_code="rag_retrieval_failed",
                        error_message=f"RAG retrieval failed for {kb_id}",
                    )
                continue

        if not chunks:
            return None, citations
        return "\n---\n".join(chunks), citations

    def _build_memory_query(self, query_text: str, top_k: int):
        """Build memory query request."""
        from app.modules.memory.application.schemas import MemoryQuery
        return MemoryQuery(query=query_text, top_k=top_k, memory_type=None, user_id=self.ctx.user_id)

    def _apply_context_window(
        self,
        messages: list[ChatMessage],
        *,
        max_messages: int | None,
        max_chars: int | None,
    ) -> list[ChatMessage]:
        """Trim trusted history while preserving published instructions and input."""
        system_messages = [message for message in messages if message.role == "system"]
        conversation = [message for message in messages if message.role != "system"]
        if max_messages is not None:
            conversation = conversation[-max_messages:]
        if max_chars is None:
            return [*system_messages, *conversation]

        remaining = max(max_chars - sum(len(message.content or "") for message in system_messages), 0)
        kept: list[ChatMessage] = []
        for msg in reversed(conversation):
            content = msg.content or ""
            if not kept:
                # The current user turn must never disappear because older context
                # or a long published system prompt consumed the configured budget.
                kept.append(ChatMessage(role=msg.role, content=content))
                remaining = max(remaining - len(content), 0)
                continue
            if len(content) <= remaining:
                kept.append(ChatMessage(role=msg.role, content=content))
                remaining -= len(content)
                continue
            if remaining <= 0:
                break
            sliced = content[-remaining:]
            kept.append(ChatMessage(role=msg.role, content=sliced))
            remaining = 0
            break
        return [*system_messages, *reversed(kept)]
