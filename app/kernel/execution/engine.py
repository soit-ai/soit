""" engine

Execution engine core entry.
"""

from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.kernel.contracts.execution_plan import ExecutionPlan
from app.kernel.trace.writer import TraceWriter
from app.kernel.execution.state_machine import StateMachine, RunStatus, StepStatus
from app.kernel.execution.scheduler import scheduler
from app.kernel.commons.time import utc_now


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
        # Create run (metrics are recorded in trace_writer)
        run = self.trace_writer.create_run(
            mode=plan.mode,
            app_version_id=plan.app_version_id,
            input_summary=str(plan.inputs)[:8192] if plan.inputs else None,
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
        from app.kernel.gateways.llm.interface import LLMGateway, ChatMessage
        from app.kernel.di import get_container
        from app.modules.domains.chat.service import ChatService
        
        # Get LLM gateway from container
        container = get_container()
        llm_gateway: LLMGateway = container.get_llm_gateway(
            ctx=self.ctx,
            trace_writer=self.trace_writer,
        )
        
        # Extract inputs
        messages_data = plan.inputs.get("messages", [])
        conversation_id = plan.inputs.get("conversation_id")
        model = plan.inputs.get("model", "model:openai:gpt-3.5-turbo")
        temperature = plan.inputs.get("temperature", 0.7)
        max_tokens = plan.inputs.get("max_tokens")
        
        # Load conversation history if conversation_id provided
        chat_service = ChatService(self.db, self.ctx)
        if conversation_id:
            try:
                # Get existing messages from conversation
                history_messages = chat_service.get_messages(
                    conversation_id=conversation_id,
                    limit=100,  # Get last 100 messages
                    offset=0,
                )
                # Convert to ChatMessage format
                existing_messages = [
                    ChatMessage(role=msg.role, content=msg.content)
                    for msg in history_messages
                ]
                # Combine with new messages
                new_messages = [
                    ChatMessage(role=msg.get("role", "user"), content=msg.get("content", ""))
                    for msg in messages_data
                ]
                all_messages = existing_messages + new_messages
            except Exception:
                # If conversation not found, use only new messages
                all_messages = [
                    ChatMessage(role=msg.get("role", "user"), content=msg.get("content", ""))
                    for msg in messages_data
                ]
        else:
            # No conversation history, use only new messages
            all_messages = [
                ChatMessage(role=msg.get("role", "user"), content=msg.get("content", ""))
                for msg in messages_data
            ]
        
        if not all_messages:
            raise ValueError("No messages provided for chat execution")
        
        # Create step for LLM call
        step = self.trace_writer.create_step(
            run_id=plan.run_id,
            step_type="llm",
            input_summary=str(all_messages)[:8192] if all_messages else None,
        )
        
        # Transition step to running
        self.state_machine.transition_step(step, "running")
        self.trace_writer.update_step_status(step.id, step.status)
        
        try:
            # Call LLM gateway
            response = await llm_gateway.chat(
                messages=all_messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            
            # Extract response text
            response_text = response.text
            
            # Save messages to conversation if conversation_id provided
            if conversation_id:
                try:
                    # Save user message(s)
                    for msg in messages_data:
                        if msg.get("role") == "user":
                            chat_service.add_message(
                                conversation_id=conversation_id,
                                role="user",
                                content=msg.get("content", ""),
                            )
                    
                    # Save assistant response
                    chat_service.add_message(
                        conversation_id=conversation_id,
                        role="assistant",
                        content=response_text,
                        metadata={
                            "model": model,
                            "tokens_prompt": response.tokens_prompt,
                            "tokens_completion": response.tokens_completion,
                        },
                    )
                except Exception:
                    # If saving fails, continue without saving
                    pass
            
            # Update step status
            self.state_machine.transition_step(step, "succeeded")
            self.trace_writer.update_step_status(
                step.id,
                "succeeded",
                output_summary=response_text[:8192],
                metrics={
                    "tokens_prompt": response.tokens_prompt,
                    "tokens_completion": response.tokens_completion,
                    "model": model,
                },
            )
            
            # Update cost
            self.trace_writer.update_cost(
                run_id=plan.run_id,
                tokens_prompt=response.tokens_prompt,
                tokens_completion=response.tokens_completion,
            )
            
            return {
                "text": response_text,
                "model": model,
                "tokens_prompt": response.tokens_prompt,
                "tokens_completion": response.tokens_completion,
                "conversation_id": conversation_id,
            }
        except Exception as e:
            # Update step status to failed
            error_message = str(e)
            self.state_machine.transition_step(step, "failed")
            self.trace_writer.update_step_status(
                step.id,
                "failed",
                error_code="CHAT_ERROR",
                error_message=error_message[:1024],
            )
            raise
    
    async def _execute_workflow(self, plan: ExecutionPlan) -> Dict[str, Any]:
        """Execute workflow mode.
        
        Args:
            plan: Execution plan.
            
        Returns:
            Workflow result.
        """
        from app.modules.domains.workflow.executor import WorkflowExecutor
        from app.modules.domains.workflow.executors.base import ExecutionContext
        from app.kernel.di import get_container
        
        # Get gateways from container
        container = get_container()
        llm_gateway = container.get_llm_gateway(
            ctx=self.ctx,
            trace_writer=self.trace_writer,
        )
        tool_gateway = container.get_tool_gateway(
            ctx=self.ctx,
            trace_writer=self.trace_writer,
        )
        vector_gateway = container.get_vector_gateway(
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
            llm_gateway=llm_gateway,
            tool_gateway=tool_gateway,
            vector_gateway=vector_gateway,
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
        from app.kernel.gateways.llm.interface import LLMGateway, ChatMessage
        from app.kernel.gateways.tools.interface import ToolGateway
        from app.kernel.di import get_container
        
        # Get gateways from container
        container = get_container()
        llm_gateway: LLMGateway = container.get_llm_gateway(
            ctx=self.ctx,
            trace_writer=self.trace_writer,
        )
        tool_gateway: ToolGateway = container.get_tool_gateway(
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
                step_type="plan",
                input_summary=f"Agent iteration {iteration}",
            )
            
            # Transition step to running
            self.state_machine.transition_step(step, "running")
            self.trace_writer.update_step_status(step.id, step.status)
            
            try:
                # Call LLM to get response or tool call
                response = await llm_gateway.chat(
                    messages=messages,
                    model=model,
                    temperature=temperature,
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
                            tool_response = await tool_gateway.invoke(
                                tool_ref=tool_ref,
                                parameters=parameters,
                                run_id=plan.run_id,
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
