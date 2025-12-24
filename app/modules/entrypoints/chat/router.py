""" router

Chat API routes (FastAPI).
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, status, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.kernel.contracts.context import RequestContext
from app.middleware.auth import get_current_context
from app.modules.domains.workflow.service import WorkflowService
from app.modules.entrypoints.chat.dependencies import get_chat_service
from app.modules.entrypoints.chat.handlers import ChatHandlers


router = APIRouter()


class ChatCompletionRequest(BaseModel):
    """Request schema for chat completion."""
    
    workflow_id: str
    """Workflow ID to execute."""
    
    messages: List[dict]
    """Chat messages."""
    
    stream: bool = False
    """Whether to stream the response."""


class ChatCompletionResponse(BaseModel):
    """Response schema for chat completion."""
    
    id: str
    """Completion ID."""
    
    workflow_id: str
    """Workflow ID."""
    
    result: dict
    """Completion result."""


@router.post("/completions", response_model=ChatCompletionResponse)
async def create_completion(
    request: ChatCompletionRequest,
    ctx: RequestContext = Depends(get_current_context),
    service: WorkflowService = Depends(get_chat_service),
):
    """Create chat completion.
    
    Args:
        request: Chat completion request.
        ctx: Request context.
        service: WorkflowService instance.
        
    Returns:
        Completion result.
    """
    handlers = ChatHandlers(service)
    result = await handlers.create_completion(
        ctx,
        request.workflow_id,
        request.messages,
        request.stream,
    )
    
    return ChatCompletionResponse(
        id=result.get("run_id", ""),
        workflow_id=request.workflow_id,
        result=result,
    )


@router.post("/stream")
async def stream_completion(
    workflow_id: str = Body(...),
    messages: List[dict] = Body(...),
    ctx: RequestContext = Depends(get_current_context),
    service: WorkflowService = Depends(get_chat_service),
):
    """Stream chat completion (SSE).
    
    Args:
        workflow_id: Workflow ID to execute.
        messages: Chat messages.
        ctx: Request context.
        service: WorkflowService instance.
        
    Returns:
        SSE stream.
    """
    handlers = ChatHandlers(service)
    
    async def generate():
        async for chunk in handlers.stream_completion(ctx, workflow_id, messages):
            yield chunk
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.get("/history")
async def get_history(
    conversation_id: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    ctx: RequestContext = Depends(get_current_context),
    service: WorkflowService = Depends(get_chat_service),
):
    """Get chat history.
    
    Args:
        conversation_id: Optional conversation ID.
        limit: Maximum number of messages.
        offset: Offset for pagination.
        ctx: Request context.
        service: WorkflowService instance.
        
    Returns:
        List of chat messages.
    """
    handlers = ChatHandlers(service)
    return await handlers.get_history(ctx, conversation_id, limit, offset)


@router.delete("/history/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: str,
    ctx: RequestContext = Depends(get_current_context),
    service: WorkflowService = Depends(get_chat_service),
):
    """Delete conversation.
    
    Args:
        conversation_id: Conversation ID.
        ctx: Request context.
        service: WorkflowService instance.
    """
    handlers = ChatHandlers(service)
    await handlers.delete_conversation(ctx, conversation_id)
