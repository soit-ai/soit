""" router

Chat API routes (FastAPI).
"""

from typing import Optional
from fastapi import APIRouter, Depends, status, Header
from fastapi.responses import StreamingResponse

from app.kernel.contracts.context import RequestContext
from app.kernel.commons.errors import ValidationError
from app.api.v1.permissions import (
    require_workspace_read_ctx,
    require_workspace_write_ctx,
)
from app.infra.db.pagination import PaginatedResponse
from app.modules.chat.application.service import ChatService
from app.modules.chat.application.schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ConversationCreate,
    ConversationUpdate,
    ConversationResponse,
    MessageResponse,
)
from app.api.v1.chat.dependencies import get_chat_service
from app.api.v1.chat.handlers import ChatHandlers


router = APIRouter()


@router.post("/completions", response_model=ChatCompletionResponse)
async def create_completion(
    request: ChatCompletionRequest,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: ChatService = Depends(get_chat_service),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """Create chat completion.
    
    Args:
        request: Chat completion request.
        ctx: Request context.
        service: ChatService instance.
        
    Returns:
        Completion result.
    """
    if request.stream:
        raise ValidationError("Use /chat/stream for streaming responses")
    handlers = ChatHandlers(service)
    return await handlers.create_completion(ctx, request, idempotency_key=idempotency_key)


@router.post("/stream")
async def stream_completion(
    request: ChatCompletionRequest,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: ChatService = Depends(get_chat_service),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """Stream chat completion (SSE).
    
    Args:
        request: Chat completion request.
        ctx: Request context.
        service: ChatService instance.
        
    Returns:
        SSE stream.
    """
    handlers = ChatHandlers(service)
    
    async def generate():
        async for chunk in handlers.stream_completion(ctx, request, idempotency_key=idempotency_key):
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


@router.get("/history")
async def get_history(
    conversation_id: Optional[str] = None,
    page_token: Optional[str] = None,
    page_size: int = 20,
    status: Optional[str] = None,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
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
    return await handlers.get_history(ctx, conversation_id, page_token, page_size, status=status)


@router.delete("/history/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: str,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
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


@router.post("/conversations", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    conversation_in: ConversationCreate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: ChatService = Depends(get_chat_service),
):
    """Create a conversation.

    Args:
        conversation_in: Conversation creation data.
        ctx: Request context.
        service: ChatService instance.

    Returns:
        Created conversation.
    """
    handlers = ChatHandlers(service)
    return await handlers.create_conversation(ctx, conversation_in)


@router.get("/conversations", response_model=PaginatedResponse[ConversationResponse])
async def list_conversations(
    page_token: Optional[str] = None,
    page_size: int = 20,
    status: Optional[str] = None,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: ChatService = Depends(get_chat_service),
):
    """List conversations.

    Args:
        page_token: Optional page token.
        page_size: Page size.
        ctx: Request context.
        service: ChatService instance.

    Returns:
        Paginated conversations.
    """
    handlers = ChatHandlers(service)
    return await handlers.list_conversations(ctx, page_token, page_size, status=status)


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: ChatService = Depends(get_chat_service),
):
    """Get conversation by ID.

    Args:
        conversation_id: Conversation ID.
        ctx: Request context.
        service: ChatService instance.

    Returns:
        Conversation details.
    """
    handlers = ChatHandlers(service)
    return await handlers.get_conversation(ctx, conversation_id)


@router.patch("/conversations/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: str,
    conversation_in: ConversationUpdate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: ChatService = Depends(get_chat_service),
):
    """Update conversation.

    Args:
        conversation_id: Conversation ID.
        conversation_in: Conversation update data.
        ctx: Request context.
        service: ChatService instance.

    Returns:
        Updated conversation.
    """
    handlers = ChatHandlers(service)
    return await handlers.update_conversation(ctx, conversation_id, conversation_in)


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation_by_id(
    conversation_id: str,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
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


@router.get("/conversations/{conversation_id}/messages", response_model=PaginatedResponse[MessageResponse])
async def list_messages(
    conversation_id: str,
    page_token: Optional[str] = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: ChatService = Depends(get_chat_service),
):
    """List messages in a conversation.

    Args:
        conversation_id: Conversation ID.
        page_token: Optional page token.
        page_size: Page size.
        ctx: Request context.
        service: ChatService instance.

    Returns:
        Paginated messages.
    """
    handlers = ChatHandlers(service)
    return await handlers.list_messages(ctx, conversation_id, page_token, page_size)
