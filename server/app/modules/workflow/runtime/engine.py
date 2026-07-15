""" engine

Execution engine core entry.
"""

import asyncio
import json
from typing import Any

from sqlalchemy.orm import Session

from app.kernel.commons.ids import generate_run_id
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.contracts.execution_plan import ExecutionPlan
from app.kernel.execution.state_machine import RunStatus, StateMachine
from app.kernel.runtime.responses.service import ResponseService
from app.kernel.runtime.runs.writer import TraceWriter


class ExecutionEngine:
    """Unified execution engine for chat/agent/workflow."""

    def __init__(
        self,
        db: Session,
        ctx: RequestContext,
        trace_writer: TraceWriter,
        response_service: ResponseService | None = None,
    ):
        """Initialize execution engine.

        Args:
            db: Database session.
            ctx: Request context.
            trace_writer: Trace writer.
        """
        self.db = db
        self.ctx = ctx
        self.trace_writer = trace_writer
        self.response_service = response_service
        self.state_machine = StateMachine()

    @staticmethod
    def _resolve_provider(model: str | None) -> str | None:
        if not model or not model.startswith("model:"):
            return None
        parts = model.split(":")
        if len(parts) >= 3:
            return parts[1]
        return None

    def _response_output_payload(
        self,
        *,
        text: str,
        model: str | None,
        finish_reason: str | None = None,
        iterations: int | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "text": text,
            "model": model,
        }
        if finish_reason:
            payload["finish_reason"] = finish_reason
        if iterations is not None:
            payload["iterations"] = iterations
        return payload

    @staticmethod
    def _response_usage_payload(
        *,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        tool_calls: int = 0,
    ) -> dict[str, Any]:
        return {
            "prompt_tokens": int(prompt_tokens or 0),
            "completion_tokens": int(completion_tokens or 0),
            "total_tokens": int(prompt_tokens or 0) + int(completion_tokens or 0),
            "tool_calls": int(tool_calls or 0),
        }

    @staticmethod
    def _tool_metrics(
        *,
        tool_ref: str,
        parameters: dict[str, Any],
        status: str,
        result: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        return {
            "tool_call": {
                "tool_name": tool_ref,
                "tool_ref": tool_ref,
                "tool_type": "builtin",
                "status": status,
                "arguments": parameters,
                "result": result or {},
                "metadata": metadata or {},
                "error_code": error_code,
                "error_message": error_message,
            }
        }

    async def execute(self, plan: ExecutionPlan) -> dict[str, Any]:
        """Execute an execution plan.

        Args:
            plan: Execution plan.

        Returns:
            Execution result.
        """
        if not plan.run_id:
            plan.run_id = generate_run_id()
        if not (plan.subject_kind and plan.subject_id):
            raise ValueError("ExecutionPlan requires subject_kind and subject_id")

        # Create run (metrics are recorded in trace_writer)
        input_summary = None
        if plan.inputs is not None:
            input_summary = json.dumps(plan.inputs, ensure_ascii=True, default=str)[:8192]

        run = self.trace_writer.create_run(
            mode=plan.mode,
            subject_kind=plan.subject_kind,
            subject_id=plan.subject_id,
            subject_version_id=plan.subject_version_id,
            input_summary=input_summary,
            run_id=plan.run_id,
        )

        # Transition to running
        self.state_machine.transition_run(run, RunStatus.RUNNING.value)
        self.trace_writer.update_run_status(run.id, run.status)

        try:
            # Execute based on mode
            if plan.mode == "chat":
                result = await self._execute_chat(plan)
            elif plan.mode == "workflow":
                result = await self._execute_workflow(plan)
            elif plan.mode == "agent":
                result = await self._execute_agent(plan)
            else:
                raise ValueError(f"Unsupported mode: {plan.mode}")

            # Transition to succeeded (metrics are recorded in trace_writer)
            self.state_machine.transition_run(run, RunStatus.SUCCEEDED.value)
            self.trace_writer.update_run_status(
                run.id,
                run.status,
                output_summary=str(result)[:8192] if result else None,
            )

            return result
        except asyncio.CancelledError:
            # Transition to canceled
            self.state_machine.transition_run(run, RunStatus.CANCELED.value)
            self.trace_writer.update_run_status(run.id, run.status)
            raise
        except Exception as e:
            # Transition to failed (metrics are recorded in trace_writer)
            error_message = str(e)
            self.state_machine.transition_run(run, RunStatus.FAILED.value)
            self.trace_writer.update_run_status(
                run.id,
                run.status,
                output_summary=error_message[:8192],
            )

            # Re-raise the exception to propagate error
            raise

    async def _execute_chat(self, plan: ExecutionPlan) -> dict[str, Any]:
        """Execute chat mode.

        Args:
            plan: Execution plan.

        Returns:
            Chat result.
        """
        from app.kernel.ports.llm.interface import ChatMessage, LLMPort
        from app.wiring import get_container

        # Get LLM port from container
        container = get_container()
        llm_port: LLMPort = container.get_llm_port(
            ctx=self.ctx,
            trace_writer=self.trace_writer,
        )

        # Extract inputs
        messages_data = plan.inputs.get("messages", [])
        model = plan.inputs.get("model", "model:openai:gpt-5.1")
        temperature = plan.inputs.get("temperature", 0.7)
        max_tokens = plan.inputs.get("max_tokens")
        top_p = plan.inputs.get("top_p")

        # Convert messages to ChatMessage format
        all_messages = [
            ChatMessage(role=msg.get("role", "user"), content=msg.get("content", ""))
            for msg in messages_data
        ]

        if not all_messages:
            raise ValueError("No messages provided for chat execution")
        step = self.trace_writer.create_step(
            run_id=plan.run_id,
            step_type="llm",
            input_summary=str(messages_data)[:8192] if messages_data else None,
        )
        self.state_machine.transition_step(step, "running")
        self.trace_writer.update_step_status(step.id, step.status)

        linked_response = None
        if self.response_service:
            linked_response = self.response_service.create_linked_response(
                run_id=plan.run_id,
                model=model,
                provider=self._resolve_provider(model),
                input_json={
                    "messages": messages_data,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "top_p": top_p,
                    "source": "execution_engine.chat",
                },
                metadata_json={
                    "source": "execution_engine.chat",
                    "step_id": step.id,
                },
            )
            linked_response = self.response_service.mark_running(linked_response)

        try:
            response = await llm_port.chat(
                messages=all_messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                run_id=plan.run_id,
            )
            response_text = response.text

            self.state_machine.transition_step(step, "succeeded")
            self.trace_writer.update_step_status(
                step.id,
                step.status,
                output_summary=response_text[:8192] if response_text else None,
                metrics={
                    "tokens_prompt": response.tokens_prompt,
                    "tokens_completion": response.tokens_completion,
                },
            )

            if linked_response:
                output_payload = self._response_output_payload(
                    text=response_text,
                    model=response.model or model,
                    finish_reason=response.finish_reason,
                )
                usage_payload = self._response_usage_payload(
                    prompt_tokens=response.tokens_prompt,
                    completion_tokens=response.tokens_completion,
                )
                linked_response = self.response_service.complete_response(
                    response=linked_response,
                    output_json=output_payload,
                    usage_json=usage_payload,
                    source="execution_engine",
                    output_event_payload={
                        "response_id": linked_response.id,
                        "run_id": linked_response.run_id,
                        "output": output_payload,
                        "usage": usage_payload,
                    },
                    completed_event_payload={
                        "response_id": linked_response.id,
                        "run_id": linked_response.run_id,
                        "status": "succeeded",
                        "usage": usage_payload,
                    },
                )

            return {
                "text": response_text,
                "model": response.model or model,
                "tokens_prompt": response.tokens_prompt,
                "tokens_completion": response.tokens_completion,
                "finish_reason": response.finish_reason,
                "response_id": linked_response.id if linked_response else None,
            }
        except Exception as e:
            self.state_machine.transition_step(step, "failed")
            self.trace_writer.update_step_status(
                step.id,
                step.status,
                output_summary=str(e)[:8192],
                error_code="CHAT_EXECUTION_ERROR",
                error_message=str(e),
            )
            if linked_response:
                linked_response = self.response_service.fail_response(
                    response=linked_response,
                    error_code="chat_execution_failed",
                    error_message=str(e),
                    source="execution_engine",
                )
            raise

    async def _execute_workflow(self, plan: ExecutionPlan) -> dict[str, Any]:
        """Execute workflow mode.

        Args:
            plan: Execution plan.

        Returns:
            Workflow result.
        """
        from app.modules.workflow.domain.models import WorkflowRun
        from app.modules.workflow.runtime.executor import WorkflowExecutor
        from app.modules.workflow.runtime.executors.base import ExecutionContext
        from app.wiring import get_container

        nodes_dict = plan.plan_data.get("nodes") or {}
        total_nodes = len(nodes_dict)
        workflow_run_row = WorkflowRun(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            run_id=plan.run_id,
            workflow_id=plan.subject_id,
            total_nodes=total_nodes,
            completed_nodes=0,
            failed_nodes=0,
            waiting_nodes=total_nodes,
            status="running",
        )
        self.db.add(workflow_run_row)
        self.db.flush()
        workflow_run_id = workflow_run_row.id

        # Get ports from container
        container = get_container()
        llm_port = container.get_llm_port(
            ctx=self.ctx,
            trace_writer=self.trace_writer,
        )
        tool_port = container.get_tool_port(
            ctx=self.ctx,
            trace_writer=self.trace_writer,
        )
        vector_port = container.get_vector_port(
            ctx=self.ctx,
            trace_writer=self.trace_writer,
        )
        plugin_runtime_port = container.get_plugin_runtime_port(
            ctx=self.ctx,
            trace_writer=self.trace_writer,
        )

        # Initialize workflow executor
        workflow_executor = WorkflowExecutor(self)

        # Create execution context
        context = ExecutionContext(
            run_id=plan.run_id,
            step_id=None,
            ctx=self.ctx,
            trace_writer=self.trace_writer,
            llm_port=llm_port,
            tool_port=tool_port,
            vector_port=vector_port,
            plugin_runtime_port=plugin_runtime_port,
            response_service=self.response_service,
            workflow_policy=plan.plan_data.get("policy", {}),
            workflow_run_id=workflow_run_id,
        )

        try:
            result = await workflow_executor.execute(plan, context)
        except Exception:
            row = self.db.get(WorkflowRun, workflow_run_id)
            if row is not None:
                row.status = "failed"
                row.updated_at = utc_now()
                self.db.add(row)
            self.db.commit()
            raise

        row = self.db.get(WorkflowRun, workflow_run_id)
        if row is not None:
            row.status = "succeeded"
            row.updated_at = utc_now()
            self.db.add(row)
        self.db.commit()

        return result

    async def _execute_agent(self, plan: ExecutionPlan) -> dict[str, Any]:
        """Execute agent mode.

        Args:
            plan: Execution plan.

        Returns:
            Agent result.
        """
        from app.kernel.ports.llm.interface import ChatMessage, LLMPort
        from app.kernel.ports.tools.interface import ToolPort
        from app.wiring import get_container

        # Get ports from container
        container = get_container()
        llm_port: LLMPort = container.get_llm_port(
            ctx=self.ctx,
            trace_writer=self.trace_writer,
        )
        tool_port: ToolPort = container.get_tool_port(
            ctx=self.ctx,
            trace_writer=self.trace_writer,
        )

        # Extract inputs
        messages_data = plan.inputs.get("messages", [])
        model = plan.inputs.get("model", "model:openai:gpt-4")
        temperature = plan.inputs.get("temperature", 0.7)
        max_iterations = plan.inputs.get("max_iterations", 10)
        tools = plan.inputs.get("tools", [])
        linked_response = None
        if self.response_service:
            linked_response = self.response_service.create_linked_response(
                run_id=plan.run_id,
                model=model,
                provider=self._resolve_provider(model),
                input_json={
                    "messages": messages_data,
                    "temperature": temperature,
                    "max_iterations": max_iterations,
                    "tools": tools,
                    "source": "execution_engine.agent",
                },
                metadata_json={"source": "execution_engine.agent"},
            )
            linked_response = self.response_service.mark_running(linked_response)

        # Convert messages to ChatMessage format
        messages = [
            ChatMessage(role=msg.get("role", "user"), content=msg.get("content", ""))
            for msg in messages_data
        ]

        # Add system message for agent behavior
        system_message = ChatMessage(
            role="system",
            content="You are a helpful AI assistant that can use tools to help answer questions. "
                   "When you need to use a tool, respond with a JSON object containing 'tool_call' "
                   "with 'tool_ref' and 'parameters' fields. Otherwise, respond normally."
        )
        messages = [system_message] + messages

        # Agent planning loop
        iteration = 0
        final_response = None
        total_prompt_tokens = 0
        total_completion_tokens = 0
        tool_call_count = 0
        finish_reason = None

        while iteration < max_iterations:
            iteration += 1

            # Create step for agent iteration
            step = self.trace_writer.create_step(
                run_id=plan.run_id,
                step_type="agent_plan",
                input_summary=f"Agent iteration {iteration}",
            )

            # Transition step to running
            self.state_machine.transition_step(step, "running")
            self.trace_writer.update_step_status(step.id, step.status)

            try:
                # Call LLM to get response or tool call
                response = await llm_port.chat(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    run_id=plan.run_id,
                )

                response_text = response.text
                total_prompt_tokens += int(response.tokens_prompt or 0)
                total_completion_tokens += int(response.tokens_completion or 0)
                finish_reason = response.finish_reason or finish_reason

                # Check if response contains tool call
                tool_call = None
                try:
                    import json
                    # Try to parse JSON tool call from response
                    if "tool_call" in response_text or "{" in response_text:
                        # Extract JSON from response
                        json_start = response_text.find("{")
                        json_end = response_text.rfind("}") + 1
                        if json_start >= 0 and json_end > json_start:
                            json_str = response_text[json_start:json_end]
                            parsed = json.loads(json_str)
                            if "tool_call" in parsed:
                                tool_call = parsed["tool_call"]
                except Exception:
                    # Not a tool call, treat as final response
                    pass

                # Add assistant message to history
                messages.append(ChatMessage(role="assistant", content=response_text))

                if tool_call and tools:
                    # Execute tool call
                    tool_ref = tool_call.get("tool_ref")
                    parameters = tool_call.get("parameters", {})

                    if tool_ref and tool_ref in [t.get("ref") or t.get("name") for t in tools]:
                        tool_call_count += 1
                        # Create step for tool execution
                        tool_step = self.trace_writer.create_step(
                            run_id=plan.run_id,
                            step_type="tool",
                            input_summary=f"Tool: {tool_ref}",
                        )

                        self.state_machine.transition_step(tool_step, "running")
                        self.trace_writer.update_step_status(tool_step.id, tool_step.status)
                        if linked_response:
                            self.response_service.append_event(
                                response=linked_response,
                                event_type="tool.call.requested",
                                payload={
                                    "response_id": linked_response.id,
                                    "run_id": linked_response.run_id,
                                    "tool_call_id": tool_step.id,
                                    "tool_name": tool_ref,
                                    "tool_type": "builtin",
                                    "step_id": tool_step.id,
                                    "status": "requested",
                                    "arguments": parameters,
                                },
                                source="execution_engine",
                            )
                            self.response_service.append_event(
                                response=linked_response,
                                event_type="tool.call.started",
                                payload={
                                    "response_id": linked_response.id,
                                    "run_id": linked_response.run_id,
                                    "tool_call_id": tool_step.id,
                                    "tool_name": tool_ref,
                                    "tool_type": "builtin",
                                    "step_id": tool_step.id,
                                    "status": "started",
                                },
                                source="execution_engine",
                            )
                        self.trace_writer.update_step_metrics(
                            tool_step.id,
                            self._tool_metrics(
                                tool_ref=tool_ref,
                                parameters=parameters,
                                status="started",
                                metadata={"source": "execution_engine.agent", "iteration": iteration},
                            ),
                        )

                        try:
                            # Invoke tool
                            tool_response = await tool_port.invoke(
                                tool_ref=tool_ref,
                                parameters=parameters,
                                run_id=plan.run_id,
                                ctx=self.ctx,
                            )

                            # Add tool result to messages
                            tool_result_message = ChatMessage(
                                role="user",
                                content=f"Tool {tool_ref} result: {json.dumps(tool_response.result) if tool_response.success else tool_response.error}"
                            )
                            messages.append(tool_result_message)

                            # Update tool step status
                            self.state_machine.transition_step(tool_step, "succeeded")
                            self.trace_writer.update_step_status(
                                tool_step.id,
                                "succeeded",
                                output_summary=str(tool_response.result)[:8192] if tool_response.success else tool_response.error,
                                metrics=self._tool_metrics(
                                    tool_ref=tool_ref,
                                    parameters=parameters,
                                    status="completed" if tool_response.success else "failed",
                                    result={"result": tool_response.result} if tool_response.success else {},
                                    metadata={"source": "execution_engine.agent", "iteration": iteration, **(tool_response.metadata or {})},
                                    error_code=None if tool_response.success else "tool_execution_failed",
                                    error_message=None if tool_response.success else tool_response.error,
                                ),
                            )
                            if linked_response:
                                self.response_service.append_event(
                                    response=linked_response,
                                    event_type="tool.call.completed" if tool_response.success else "tool.call.failed",
                                    payload={
                                        "response_id": linked_response.id,
                                        "run_id": linked_response.run_id,
                                        "tool_call_id": tool_step.id,
                                        "tool_name": tool_ref,
                                        "tool_type": "builtin",
                                        "step_id": tool_step.id,
                                        "status": "completed" if tool_response.success else "failed",
                                        "result": {"result": tool_response.result} if tool_response.success else {},
                                        "metadata": tool_response.metadata or {},
                                        "error": None if tool_response.success else {
                                            "code": "tool_execution_failed",
                                            "message": tool_response.error,
                                        },
                                    },
                                    source="execution_engine",
                                )
                        except Exception as e:
                            # Tool execution failed
                            error_message = str(e)
                            self.state_machine.transition_step(tool_step, "failed")
                            self.trace_writer.update_step_status(
                                tool_step.id,
                                "failed",
                                metrics=self._tool_metrics(
                                    tool_ref=tool_ref,
                                    parameters=parameters,
                                    status="failed",
                                    metadata={"source": "execution_engine.agent", "iteration": iteration},
                                    error_code="tool_execution_failed",
                                    error_message=error_message,
                                ),
                                error_code="TOOL_ERROR",
                                error_message=error_message[:1024],
                            )
                            if linked_response:
                                self.response_service.append_event(
                                    response=linked_response,
                                    event_type="tool.call.failed",
                                    payload={
                                        "response_id": linked_response.id,
                                        "run_id": linked_response.run_id,
                                        "tool_call_id": tool_step.id,
                                        "tool_name": tool_ref,
                                        "tool_type": "builtin",
                                        "step_id": tool_step.id,
                                        "status": "failed",
                                        "error": {"code": "tool_execution_failed", "message": error_message},
                                    },
                                    source="execution_engine",
                                )
                            # Add error to messages
                            messages.append(ChatMessage(
                                role="user",
                                content=f"Tool {tool_ref} failed: {error_message}"
                            ))
                    else:
                        # Tool not found, treat as final response
                        final_response = response_text
                        break
                else:
                    # No tool call, this is the final response
                    final_response = response_text
                    break

                # Update planning step status
                self.state_machine.transition_step(step, "succeeded")
                self.trace_writer.update_step_status(
                    step.id,
                    "succeeded",
                    output_summary=f"Iteration {iteration} completed",
                )

            except Exception as e:
                # Planning iteration failed
                error_message = str(e)
                self.state_machine.transition_step(step, "failed")
                self.trace_writer.update_step_status(
                    step.id,
                    "failed",
                    error_code="AGENT_ERROR",
                    error_message=error_message[:1024],
                )
                raise

        if not final_response:
            final_response = "Agent reached maximum iterations without completing task."

        if linked_response:
            output_payload = self._response_output_payload(
                text=final_response,
                model=model,
                finish_reason=finish_reason,
                iterations=iteration,
            )
            usage_payload = self._response_usage_payload(
                prompt_tokens=total_prompt_tokens,
                completion_tokens=total_completion_tokens,
                tool_calls=tool_call_count,
            )
            linked_response = self.response_service.complete_response(
                response=linked_response,
                output_json=output_payload,
                usage_json=usage_payload,
                source="execution_engine",
                output_event_payload={
                    "response_id": linked_response.id,
                    "run_id": linked_response.run_id,
                    "output": output_payload,
                    "usage": usage_payload,
                },
                completed_event_payload={
                    "response_id": linked_response.id,
                    "run_id": linked_response.run_id,
                    "status": "succeeded",
                    "usage": usage_payload,
                    "tool_calls": tool_call_count,
                },
            )

        return {
            "output": final_response,
            "iterations": iteration,
            "model": model,
            "response_id": linked_response.id if linked_response else None,
        }
