""" engine

Execution engine core entry.
"""

from typing import Dict, Any
import asyncio
import json
from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.kernel.contracts.execution_plan import ExecutionPlan
from app.kernel.trace.writer import TraceWriter
from app.kernel.execution.state_machine import StateMachine, RunStatus
from app.kernel.commons.ids import generate_run_id


class ExecutionEngine:
    """Unified execution engine for chat/agent/workflow."""
    
    def __init__(
        self,
        db: Session,
        ctx: RequestContext,
        trace_writer: TraceWriter,
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
        self.state_machine = StateMachine()
    
    async def execute(self, plan: ExecutionPlan) -> Dict[str, Any]:
        """Execute an execution plan.
        
        Args:
            plan: Execution plan.
            
        Returns:
            Execution result.
        """
        if not plan.run_id:
            plan.run_id = generate_run_id()
        if not plan.app_id or not plan.app_version_id:
            raise ValueError("ExecutionPlan requires app_id and app_version_id")

        # Create run (metrics are recorded in trace_writer)
        input_summary = None
        if plan.inputs is not None:
            input_summary = json.dumps(plan.inputs, ensure_ascii=True, default=str)[:8192]

        run = self.trace_writer.create_run(
            mode=plan.mode,
            app_id=plan.app_id,
            app_version_id=plan.app_version_id,
            app_type=plan.mode,
            input_summary=input_summary,
            run_id=plan.run_id,
        )
        
        # Transition to running
        self.state_machine.transition_run(run, RunStatus.RUNNING.value)
        self.trace_writer.update_run_status(run.id, run.status)
        
        try:
            # Execute based on mode
            if plan.mode in ("chat", "bot"):
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
    
    async def _execute_chat(self, plan: ExecutionPlan) -> Dict[str, Any]:
        """Execute chat mode.
        
        Args:
            plan: Execution plan.
            
        Returns:
            Chat result.
        """
        from app.kernel.ports.llm.interface import LLMPort, ChatMessage
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
        
        try:
            # Call LLM port
            response = await llm_port.chat(
                messages=all_messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                run_id=plan.run_id,
            )
            
            # Extract response text
            response_text = response.text
            
            return {
                "text": response_text,
                "model": response.model or model,
                "tokens_prompt": response.tokens_prompt,
                "tokens_completion": response.tokens_completion,
                "finish_reason": response.finish_reason,
            }
        except Exception as e:
            raise
    
    async def _execute_workflow(self, plan: ExecutionPlan) -> Dict[str, Any]:
        """Execute workflow mode.
        
        Args:
            plan: Execution plan.
            
        Returns:
            Workflow result.
        """
        from app.modules.workflow.runtime.executor import WorkflowExecutor
        from app.modules.workflow.runtime.executors.base import ExecutionContext
        from app.wiring import get_container
        
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
            workflow_policy=plan.plan_data.get("policy", {}),
        )
        
        # Execute workflow
        result = await workflow_executor.execute(plan, context)
        
        return result
    
    async def _execute_agent(self, plan: ExecutionPlan) -> Dict[str, Any]:
        """Execute agent mode.
        
        Args:
            plan: Execution plan.
            
        Returns:
            Agent result.
        """
        from app.kernel.ports.llm.interface import LLMPort, ChatMessage
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
                        # Create step for tool execution
                        tool_step = self.trace_writer.create_step(
                            run_id=plan.run_id,
                            step_type="tool",
                            input_summary=f"Tool: {tool_ref}",
                        )
                        
                        self.state_machine.transition_step(tool_step, "running")
                        self.trace_writer.update_step_status(tool_step.id, tool_step.status)
                        
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
                            )
                        except Exception as e:
                            # Tool execution failed
                            error_message = str(e)
                            self.state_machine.transition_step(tool_step, "failed")
                            self.trace_writer.update_step_status(
                                tool_step.id,
                                "failed",
                                error_code="TOOL_ERROR",
                                error_message=error_message[:1024],
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
        
        return {
            "output": final_response,
            "iterations": iteration,
            "model": model,
        }
