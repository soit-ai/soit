""" router

SSE API routes (FastAPI).
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, status, Body
from fastapi.responses import StreamingResponse

from app.kernel.contracts.context import RequestContext
from app.api.v1.permissions import require_workspace_write_ctx, require_workspace_read_ctx
from app.modules.workflow.application.app_facade import WorkflowAppFacadeService
from app.api.v1.workflow.dependencies import get_workflow_service
from app.api.v1.sse.handlers import SSEHandlers


router = APIRouter()


@router.post("/execution")
async def stream_execution(
    app_id: str = Body(...),
    inputs: dict = Body(...),
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: WorkflowAppFacadeService = Depends(get_workflow_service),
):
    """Stream workflow execution updates (SSE).
    
    Args:
        app_id: App ID.
        inputs: Workflow inputs.
        ctx: Request context.
        service: WorkflowAppFacadeService instance.
        
    Returns:
        SSE stream.
    """
    handlers = SSEHandlers(service)
    
    async def generate():
        async for chunk in handlers.stream_execution(ctx, app_id, inputs):
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
    app_id: str = Body(...),
    messages: List[dict] = Body(...),
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: WorkflowAppFacadeService = Depends(get_workflow_service),
):
    """Stream chat completion (SSE).
    
    Args:
        app_id: App ID.
        messages: Chat messages.
        ctx: Request context.
        service: WorkflowAppFacadeService instance.
        
    Returns:
        SSE stream.
    """
    handlers = SSEHandlers(service)
    
    async def generate():
        async for chunk in handlers.stream_chat(ctx, app_id, messages):
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


@router.get("/runs/{run_id}")
async def stream_run(
    run_id: str,
    last_event_id: Optional[str] = None,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: WorkflowAppFacadeService = Depends(get_workflow_service),
):
    """Stream run events and replay missed steps when possible."""
    handlers = SSEHandlers(service)

    async def generate():
        async for chunk in handlers.stream_run(ctx, run_id, last_event_id=last_event_id):
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
