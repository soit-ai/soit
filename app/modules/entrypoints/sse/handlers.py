""" handlers

SSE request handlers.
"""

from typing import AsyncGenerator
import json

from app.kernel.contracts.context import RequestContext
from app.modules.domains.workflow.service import WorkflowService


class SSEHandlers:
    """Handlers for SSE endpoints."""
    
    def __init__(self, workflow_service: WorkflowService):
        """Initialize SSE handlers.
        
        Args:
            workflow_service: WorkflowService instance.
        """
        self.workflow_service = workflow_service
    
    async def stream_execution(
        self,
        ctx: RequestContext,
        workflow_id: str,
        inputs: dict,
    ) -> AsyncGenerator[str, None]:
        """Stream workflow execution updates (SSE).
        
        Args:
            ctx: Request context.
            workflow_id: Workflow ID.
            inputs: Workflow inputs.
            
        Yields:
            SSE formatted data chunks.
        """
        from app.kernel.commons.ids import generate_ulid
        from app.kernel.execution.engine import ExecutionEngine
        from app.kernel.trace.writer import TraceWriter
        from app.kernel.trace.models import RunStep, Run
        from sqlalchemy import select, and_
        import asyncio
        
        run_id = generate_ulid()
        
        # Send initial event
        yield f"event: start\n"
        yield f"data: {json.dumps({'run_id': run_id, 'status': 'started'})}\n\n"
        
        try:
            # Compile workflow
            execution_plan = self.workflow_service.compile_workflow(workflow_id, inputs, run_id)
            
            yield f"event: compiled\n"
            yield f"data: {json.dumps({'run_id': run_id, 'status': 'compiled'})}\n\n"
            
            # Initialize execution engine
            db = self.workflow_service.db
            trace_writer = TraceWriter(db, ctx)
            execution_engine = ExecutionEngine(
                db=db,
                ctx=ctx,
                trace_writer=trace_writer,
            )
            
            # Start execution in background
            execution_task = asyncio.create_task(execution_engine.execute(execution_plan))
            
            # Monitor step updates
            last_step_count = 0
            last_step_ids = set()
            max_iterations = 10000  # Prevent infinite loop
            iteration = 0
            
            while not execution_task.done() and iteration < max_iterations:
                iteration += 1
                
                # Query for new steps
                steps_query = select(RunStep).where(
                    and_(
                        RunStep.run_id == run_id,
                        RunStep.tenant_id == ctx.tenant_id,
                        RunStep.workspace_id == ctx.workspace_id,
                    )
                ).order_by(RunStep.created_at)
                steps = list(db.exec(steps_query).all())
                
                # Send updates for new steps
                for step in steps[last_step_count:]:
                    if step.id not in last_step_ids:
                        yield f"event: step\n"
                        yield f"data: {json.dumps({
                            'run_id': run_id,
                            'step_id': step.step_id or step.id,
                            'step_type': step.step_type,
                            'status': step.status,
                            'input_summary': step.input_summary[:200] if step.input_summary else None,
                            'output_summary': step.output_summary[:200] if step.output_summary else None,
                        })}\n\n"
                        last_step_ids.add(step.id)
                
                last_step_count = len(steps)
                
                # Small delay to avoid busy waiting
                await asyncio.sleep(0.1)
            
            # Wait for execution to complete
            try:
                result = await execution_task
            except Exception as exec_error:
                # Execution failed
                yield f"event: error\n"
                yield f"data: {json.dumps({'run_id': run_id, 'error': str(exec_error)})}\n\n"
                return
            
            # Get final run status
            run = db.get(Run, run_id)
            
            if run:
                yield f"event: complete\n"
                yield f"data: {json.dumps({
                    'run_id': run_id,
                    'status': run.status,
                    'output_summary': run.output_summary[:500] if run.output_summary else None,
                })}\n\n"
            else:
                yield f"event: complete\n"
                yield f"data: {json.dumps({'run_id': run_id, 'status': 'completed'})}\n\n"
            
        except Exception as e:
            yield f"event: error\n"
            yield f"data: {json.dumps({'run_id': run_id, 'error': str(e)})}\n\n"
    
    async def stream_chat(
        self,
        ctx: RequestContext,
        workflow_id: str,
        messages: list,
    ) -> AsyncGenerator[str, None]:
        """Stream chat completion (SSE).
        
        Args:
            ctx: Request context.
            workflow_id: Workflow ID.
            messages: Chat messages.
            
        Yields:
            SSE formatted data chunks.
        """
        inputs = {
            "messages": messages,
        }
        
        async for chunk in self.stream_execution(ctx, workflow_id, inputs):
            yield chunk

