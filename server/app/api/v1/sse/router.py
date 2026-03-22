""" router

SSE API routes (FastAPI).
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.kernel.contracts.context import RequestContext
from app.api.v1.permissions import require_workspace_write_ctx, require_workspace_read_ctx
from app.modules.workflow.application.service import WorkflowService
from app.api.v1.workflow.dependencies import get_workflow_service
from app.api.v1.sse.handlers import SSEHandlers


router = APIRouter()


class WorkflowExecutionStreamRequest(BaseModel):
    workflow_id: str
    inputs: dict = Field(default_factory=dict)

    def resolved_workflow_id(self) -> str:
        if not self.workflow_id:
            raise HTTPException(status_code=400, detail="workflow_id is required")
        return self.workflow_id


class WorkflowChatStreamRequest(BaseModel):
    workflow_id: str
    messages: List[dict] = Field(default_factory=list)

    def resolved_workflow_id(self) -> str:
        if not self.workflow_id:
            raise HTTPException(status_code=400, detail="workflow_id is required")
        return self.workflow_id


@router.post("/execution")
async def stream_execution(
    payload: WorkflowExecutionStreamRequest,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: WorkflowService = Depends(get_workflow_service),
):
    """Stream workflow execution updates (SSE).
    
    Args:
        payload: Workflow stream payload.
        ctx: Request context.
        service: WorkflowService instance.
        
    Returns:
        SSE stream.
    """
    handlers = SSEHandlers(service)
    workflow_id = payload.resolved_workflow_id()
    
    async def generate():
        async for chunk in handlers.stream_execution(ctx, workflow_id, payload.inputs):
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
    payload: WorkflowChatStreamRequest,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: WorkflowService = Depends(get_workflow_service),
):
    """Stream chat completion (SSE).
    
    Args:
        payload: Workflow chat stream payload.
        ctx: Request context.
        service: WorkflowService instance.
        
    Returns:
        SSE stream.
    """
    handlers = SSEHandlers(service)
    workflow_id = payload.resolved_workflow_id()
    
    async def generate():
        async for chunk in handlers.stream_chat(ctx, workflow_id, payload.messages):
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
    service: WorkflowService = Depends(get_workflow_service),
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
