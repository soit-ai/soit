""" service

Agent domain service.
"""

import time
from typing import Optional, Dict, Any, List

from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.kernel.commons.errors import ValidationError
from app.kernel.commons.ids import generate_run_id
from app.kernel.responses.service import ResponseService
from app.kernel.trace.writer import TraceWriter
from app.kernel.ports.common.rate_limiter import RateLimiter
from app.kernel.ports.llm.interface import LLMPort, ChatMessage, ToolCall
from app.kernel.ports.tools.interface import ToolPort
from app.settings.settings import settings
from app.modules.agent.application.schemas import AgentRunRequest
from app.modules.agent.runtime.planner import AgentPlanner
from app.modules.agent.runtime.executor import AgentExecutor
from app.modules.agent.runtime.verifier import AgentVerifier
from app.modules.agent.runtime.emitter import EventEmitter, noop_emitter
from app.adapters.tools.resolver import ToolResolver
from app.modules.memory.application.service import MemoryService
from app.kernel.identity.guard import workspace_guard


class AgentService:
    """Agent service for plan-execute-verify."""

    def __init__(
        self,
        db: Session,
        ctx: RequestContext,
        llm_port: LLMPort,
        tool_port: ToolPort,
        tool_resolver: Optional[ToolResolver] = None,
        memory_service: Optional[MemoryService] = None,
        response_service: Optional[ResponseService] = None,
        trace_writer: Optional[TraceWriter] = None,
        rate_limiter: Optional[RateLimiter] = None,
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
        self.planner = AgentPlanner(llm_port)
        self.executor = AgentExecutor(tool_port)
        self.verifier = AgentVerifier(llm_port)

    def _resolve_agent_trace_subject(self) -> tuple[str, str]:
        return self.ctx.workspace_id, "agent-runtime:v1"

    @workspace_guard("write")
    async def run(
        self,
        data: AgentRunRequest,
        *,
        existing_run_id: Optional[str] = None,
        response_id: Optional[str] = None,
        event_emitter: Optional[EventEmitter] = None,
    ) -> Dict[str, Any]:
        """Run agent loop."""
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
                )
                run_id = run.id
                self.trace_writer.update_run_status(run_id, "running")

        messages = [ChatMessage(role=m.role, content=m.content) for m in data.messages]
        messages = self._apply_context_window(
            messages,
            max_messages=data.context_window_messages,
            max_chars=data.context_window_chars,
        )
        memory_context = None

        if self.memory_service:
            query_text = data.memory_query or data.messages[-1].content
            try:
                results = await self.memory_service.query_memory(
                    self._build_memory_query(query_text=query_text, top_k=data.memory_top_k),
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
        if data.knowledge_refs:
            query_text = data.messages[-1].content
            rag_context = await self._retrieve_rag_context(
                knowledge_refs=data.knowledge_refs,
                query=query_text,
                top_k=data.rag_top_k,
                run_id=run_id,
            )

        if rag_context and data.rag_strategy == "system_message":
            messages = [ChatMessage(role="system", content=f"Retrieved context:\n{rag_context}")] + messages
            rag_context = None

        model = data.model or "model:openai:gpt-5.1"
        iterations = 0
        final_response = ""
        tokens_prompt = 0
        tokens_completion = 0
        finish_reason = None
        tool_calls = 0
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
            parameters: Dict[str, Any],
            status: str,
            result: Optional[Dict[str, Any]] = None,
            metadata: Optional[Dict[str, Any]] = None,
            error_code: Optional[str] = None,
            error_message: Optional[str] = None,
        ) -> Dict[str, Any]:
            return {
                "tool_call": {
                    "tool_name": tool_ref,
                    "tool_ref": tool_ref,
                    "tool_type": "builtin",
                    "status": status,
                    "arguments": parameters or {},
                    "result": result or {},
                    "metadata": metadata or {},
                    "error_code": error_code,
                    "error_message": error_message,
                }
            }

        # Resolve tool definitions for function calling
        tool_definitions = None
        if self.tool_resolver and data.tool_refs:
            tool_definitions = await self.tool_resolver.resolve(data.tool_refs, self.ctx)

        try:
            await emit("agent.run.started", {"run_id": run_id})
            while iterations < data.max_iterations:
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
                tokens_prompt += plan.tokens_prompt
                tokens_completion += plan.tokens_completion
                finish_reason = plan.finish_reason or finish_reason
                await emit("agent.plan.completed", {"action": plan.action, "iteration": iterations})
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
                        if data.tool_refs and tc.name not in data.tool_refs:
                            raise ValidationError(f"Tool not allowed: {tc.name}")

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
                                    parameters=tc.arguments,
                                    status="started",
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
                                    "tool_type": "builtin",
                                    "step_id": tool_step_id,
                                    "status": "requested",
                                    "arguments": tc.arguments,
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
                                    "tool_type": "builtin",
                                    "step_id": tool_step_id,
                                    "status": "started",
                                },
                                source="agent",
                            )
                        try:
                            tool_response = await self.executor.execute_tool(
                                tool_ref=tc.name,
                                parameters=tc.arguments,
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
                                        parameters=tc.arguments,
                                        status="failed",
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
                                        "tool_type": "builtin",
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
                        await emit("agent.tool.completed", {"tool_ref": tc.name, "success": tool_response.success})

                        if self.trace_writer and tool_step_id:
                            status = "succeeded" if tool_response.success else "failed"
                            self.trace_writer.update_step_status(
                                tool_step_id,
                                status,
                                output_summary=tool_content[:8192],
                                metrics={
                                    **(tool_response.metadata or {}),
                                    **build_tool_metrics(
                                        tool_ref=tc.name,
                                        parameters=tc.arguments,
                                        status="completed" if tool_response.success else "failed",
                                        result={"result": tool_response.result} if tool_response.success else {},
                                        metadata={"source": "agent.tool", "iteration": iterations, **(tool_response.metadata or {})},
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
                                    "tool_type": "builtin",
                                    "step_id": tool_step_id,
                                    "status": "completed" if tool_response.success else "failed",
                                    "result": {"result": tool_response.result} if tool_response.success else {},
                                    "metadata": tool_response.metadata or {},
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
                    await emit("agent.response.completed", {"output": final_response})
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

            await emit("agent.run.completed", {"run_id": run_id, "status": "succeeded"})
            if self.trace_writer:
                self.trace_writer.update_run_status(
                    run_id,
                    "succeeded",
                    output_summary=final_response[:8192],
                )
        except Exception as exc:
            if self.trace_writer:
                self.trace_writer.update_run_status(
                    run_id,
                    "failed",
                    output_summary=str(exc)[:8192],
                )
            raise

        return {
            "run_id": run_id,
            "output": final_response,
            "model": model,
            "iterations": iterations,
            "tokens_prompt": tokens_prompt,
            "tokens_completion": tokens_completion,
            "finish_reason": finish_reason,
            "tool_calls": tool_calls,
            "llm_calls": llm_calls,
            "failures": failures,
            "budget_exceeded": budget_exceeded,
            "budget_reason": budget_reason,
            "cost_total": cost_total,
        }

    def _get_cost_total(self, run_id: str, currency: str) -> float:
        """Get total cost for a run."""
        from app.kernel.trace.models import RunCostEntry
        from sqlalchemy import select, func, and_

        query = select(func.coalesce(func.sum(RunCostEntry.amount), 0)).where(
            and_(
                RunCostEntry.run_id == run_id,
                RunCostEntry.tenant_id == self.ctx.tenant_id,
                RunCostEntry.workspace_id == self.ctx.workspace_id,
                RunCostEntry.currency == currency,
            )
        )
        result = self.db.exec(query).one()
        if isinstance(result, (list, tuple)):
            value = result[0]
        else:
            value = result
        return float(value or 0)

    async def _retrieve_rag_context(
        self,
        knowledge_refs: List[str],
        query: str,
        top_k: int = 5,
        run_id: Optional[str] = None,
    ) -> Optional[str]:
        """Retrieve context from knowledge bases for RAG injection."""
        from app.modules.knowledge.application.tools import knowledge_query

        chunks: List[str] = []
        for ref in knowledge_refs:
            # knowledge_refs are in format "knowledge:kb_id" or just "kb_id"
            kb_id = ref.split(":")[-1] if ":" in ref else ref
            try:
                response = await knowledge_query(
                    knowledge_id=kb_id,
                    query=query,
                    top_k=top_k,
                    ctx={
                        "tenant_id": self.ctx.tenant_id,
                        "workspace_id": self.ctx.workspace_id,
                        "user_id": self.ctx.user_id,
                    },
                )
                for result in response.get("results") or []:
                    text = result.get("text") or result.get("content") or ""
                    if text:
                        chunks.append(text)
            except Exception:
                continue

        if not chunks:
            return None
        return "\n---\n".join(chunks)

    def _build_memory_query(self, query_text: str, top_k: int):
        """Build memory query request."""
        from app.modules.memory.application.schemas import MemoryQuery
        return MemoryQuery(query=query_text, top_k=top_k, memory_type=None, user_id=self.ctx.user_id)

    def _apply_context_window(
        self,
        messages: List[ChatMessage],
        *,
        max_messages: Optional[int],
        max_chars: Optional[int],
    ) -> List[ChatMessage]:
        """Trim messages to the configured context window."""
        trimmed = list(messages)
        if max_messages is not None:
            trimmed = trimmed[-max_messages:]
        if max_chars is None:
            return trimmed

        remaining = max_chars
        kept = []
        for msg in reversed(trimmed):
            content = msg.content or ""
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
        return list(reversed(kept))
