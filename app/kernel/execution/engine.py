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
        # Create run
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
            
            # Transition to succeeded
            self.state_machine.transition_run(run, RunStatus.SUCCEEDED.value)
            self.trace_writer.update_run_status(
                run.id,
                run.status,
                output_summary=str(result)[:8192] if result else None,
            )
            
            return result
        except Exception as e:
            # Transition to failed
            self.state_machine.transition_run(run, RunStatus.FAILED.value)
            self.trace_writer.update_run_status(
                run.id,
                run.status,
                output_summary=str(e)[:8192],
            )
            raise
    
    async def _execute_chat(self, plan: ExecutionPlan) -> Dict[str, Any]:
        """Execute chat mode.
        
        Args:
            plan: Execution plan.
            
        Returns:
            Chat result.
        """
        # Placeholder: In production, implement chat execution
        # This would call LLM gateway via policy gateway
        return {"text": "Chat execution placeholder"}
    
    async def _execute_workflow(self, plan: ExecutionPlan) -> Dict[str, Any]:
        """Execute workflow mode.
        
        Args:
            plan: Execution plan.
            
        Returns:
            Workflow result.
        """
        from app.modules.domains.workflow.executor import WorkflowExecutor
        from app.modules.domains.workflow.executors.base import ExecutionContext
        from app.adapters.openai_llm import OpenAILLMGateway
        from app.adapters.http_tools import HTTPToolsGateway
        from app.adapters.milvus_vector import MilvusVectorGateway
        
        # Initialize gateways (TODO: Use dependency injection in production)
        llm_gateway = OpenAILLMGateway()
        tool_gateway = HTTPToolsGateway()
        vector_gateway = MilvusVectorGateway()
        
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
        # Placeholder: In production, implement agent execution
        # This would run agent planning loop
        return {"output": "Agent execution placeholder"}
