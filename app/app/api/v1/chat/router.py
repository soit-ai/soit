""" router

Chat API routes (FastAPI).
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, status, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.kernel.contracts.context import RequestContext
from app.middleware.auth import get_current_context
from app.modules.chat.application.service import ChatService
from app.modules.workflow.application.service import WorkflowService
from app.api.v1.chat.dependencies import get_chat_service
from app.api.v1.chat.handlers import ChatHandlers
from app.api.v1.workflow.dependencies import get_workflow_service


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
    service: ChatService = Depends(get_chat_service),
    workflow_service: WorkflowService = Depends(get_workflow_service),
):
    """Create chat completion.
    
    Args:
        request: Chat completion request.
        ctx: Request context.
        service: ChatService instance.
        workflow_service: WorkflowService instance.
        
    Returns:
        Completion result.
    """
    handlers = ChatHandlers(service, workflow_service)
    result = await handlers.create_completion(
        ctx, request.workflow_id, request.messages, request.stream, workflow_service
    )
    return ChatCompletionResponse(
        id=result.get("run_id", "unknown"),
        workflow_id=request.workflow_id,
        result=result,
    )


@router.post("/stream")
async def stream_completion(
    workflow_id: str = Body(...),
    messages: List[dict] = Body(...),
    ctx: RequestContext = Depends(get_current_context),
    service: ChatService = Depends(get_chat_service),
    workflow_service: WorkflowService = Depends(get_workflow_service),
):
    """Stream chat completion (SSE).
    
    Args:
        workflow_id: Workflow ID to execute.
        messages: Chat messages.
        ctx: Request context.
        service: ChatService instance.
        workflow_service: WorkflowService instance.
        
    Returns:
        SSE stream.
    """
    handlers = ChatHandlers(service, workflow_service)
    
    async def generate():
        async for chunk in handlers.stream_completion(ctx, workflow_id, messages, workflow_service):
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
    page_token: Optional[str] = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(get_current_context),
    service: ChatService = Depends(get_chat_service),
):
    """Get chat history.
    
    Args:
        conversation_id: Optional conversation ID.
        page_token: Optional page token.
        page_size: Page size.
        ctx: Request context.
        service: ChatService instance.
        
    Returns:
        Paginated chat history.
    """
    handlers = ChatHandlers(service)
    return await handlers.get_history(ctx, conversation_id, page_token, page_size)


@router.delete("/history/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: str,
    ctx: RequestContext = Depends(get_current_context),
    service: ChatService = Depends(get_chat_service),
):
    """Delete conversation.
    
    Args:
        conversation_id: Conversation ID.
        ctx: Request context.
        service: ChatService instance.
    """
    handlers = ChatHandlers(service)
    await handlers.delete_conversation(ctx, conversation_id)
