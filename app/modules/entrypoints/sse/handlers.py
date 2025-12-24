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
        
        run_id = generate_ulid()
        
        # Send initial event
        yield f"event: start\n"
        yield f"data: {json.dumps({'run_id': run_id, 'status': 'started'})}\n\n"
        
        try:
            # Compile workflow
            execution_plan = self.workflow_service.compile_workflow(workflow_id, inputs, run_id)
            
            yield f"event: compiled\n"
            yield f"data: {json.dumps({'run_id': run_id, 'status': 'compiled'})}\n\n"
            
            # TODO: Execute workflow and stream updates
            # For now, send placeholder updates
            yield f"event: step\n"
            yield f"data: {json.dumps({'run_id': run_id, 'step_id': 'step_1', 'status': 'running'})}\n\n"
            
            yield f"event: step\n"
            yield f"data: {json.dumps({'run_id': run_id, 'step_id': 'step_1', 'status': 'completed'})}\n\n"
            
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

