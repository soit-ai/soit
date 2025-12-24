""" router

SSE API routes (FastAPI).
"""

from typing import List
from fastapi import APIRouter, Depends, status, Body
from fastapi.responses import StreamingResponse

from app.kernel.contracts.context import RequestContext
from app.middleware.auth import get_current_context
from app.modules.domains.workflow.service import WorkflowService
from app.modules.entrypoints.workflow.dependencies import get_workflow_service
from app.modules.entrypoints.sse.handlers import SSEHandlers


router = APIRouter()


@router.post("/execution")
async def stream_execution(
    workflow_id: str = Body(...),
    inputs: dict = Body(...),
    ctx: RequestContext = Depends(get_current_context),
    service: WorkflowService = Depends(get_workflow_service),
):
    """Stream workflow execution updates (SSE).
    
    Args:
        workflow_id: Workflow ID.
        inputs: Workflow inputs.
        ctx: Request context.
        service: WorkflowService instance.
        
    Returns:
        SSE stream.
    """
    handlers = SSEHandlers(service)
    
    async def generate():
        async for chunk in handlers.stream_execution(ctx, workflow_id, inputs):
            yield chunk
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable buffering for nginx
        },
    )


@router.post("/chat")
async def stream_chat(
    workflow_id: str = Body(...),
    messages: List[dict] = Body(...),
    ctx: RequestContext = Depends(get_current_context),
    service: WorkflowService = Depends(get_workflow_service),
):
    """Stream chat completion (SSE).
    
    Args:
        workflow_id: Workflow ID.
        messages: Chat messages.
        ctx: Request context.
        service: WorkflowService instance.
        
    Returns:
        SSE stream.
    """
    handlers = SSEHandlers(service)
    
    async def generate():
        async for chunk in handlers.stream_chat(ctx, workflow_id, messages):
            yield chunk
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

