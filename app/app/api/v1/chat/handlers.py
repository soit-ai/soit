""" handlers

Chat request handlers (thin orchestration).
"""

from typing import Optional, AsyncGenerator, Dict, Any, Iterable
import json

from app.kernel.contracts.context import RequestContext
from app.modules.chat.application.service import ChatService
from app.modules.chat.application.schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ConversationCreate,
    ConversationUpdate,
    ConversationResponse,
    MessageResponse,
)
from app.infra.db.pagination import PaginatedResponse, parse_page_params
from app.api.v1.schemas.chat import serialize_conversation, serialize_message


class ChatHandlers:
    """Handlers for chat API endpoints."""
    
    def __init__(self, service: ChatService):
        """Initialize chat handlers.
        
        Args:
            service: ChatService instance.
        """
        self.service = service

    def _chunk_text(self, text: str, chunk_size: int = 80) -> Iterable[str]:
        """Split text into fixed-size chunks.

        Args:
            text: Input text.
            chunk_size: Chunk size.

        Returns:
            Iterable of text chunks.
        """
        if not text:
            return []
        return (text[i : i + chunk_size] for i in range(0, len(text), chunk_size))
    
    async def create_completion(
        self,
        ctx: RequestContext,
        data: ChatCompletionRequest,
    ) -> ChatCompletionResponse:
        """Create chat completion.
        
        Args:
            ctx: Request context.
            data: Chat completion request.
            
        Returns:
            Completion result.
        """
        result = await self.service.create_completion(data)
        return ChatCompletionResponse(
            run_id=result["run_id"],
            conversation_id=result["conversation"].id,
            message=MessageResponse.model_validate(result["message"]),
            model=result["model"],
            tokens_prompt=result["tokens_prompt"],
            tokens_completion=result["tokens_completion"],
            finish_reason=result["finish_reason"],
        )
    
    async def stream_completion(
        self,
        ctx: RequestContext,
        data: ChatCompletionRequest,
    ) -> AsyncGenerator[str, None]:
        """Stream chat completion (SSE).
        
        Args:
            ctx: Request context.
            data: Chat completion request.
            
        Yields:
            SSE formatted data chunks.
        """
        result = await self.service.create_completion(data)
        run_id = result["run_id"]
        conversation_id = result["conversation"].id
        message = result["message"]

        yield f"event: start\ndata: {json.dumps({'run_id': run_id, 'conversation_id': conversation_id})}\n\n"

        for chunk in self._chunk_text(message.content):
            yield f"event: delta\ndata: {json.dumps({'run_id': run_id, 'delta': chunk})}\n\n"

        yield f"event: complete\ndata: {json.dumps({'run_id': run_id, 'message_id': message.id, 'model': result['model'], 'tokens_prompt': result['tokens_prompt'], 'tokens_completion': result['tokens_completion'], 'finish_reason': result['finish_reason']})}\n\n"
    
    async def get_history(
        self,
        ctx: RequestContext,
        conversation_id: Optional[str] = None,
        page_token: Optional[str] = None,
        page_size: int = 20,
    ) -> PaginatedResponse[Dict[str, Any]]:
        """Get chat history.
        
        Args:
            ctx: Request context.
            conversation_id: Optional conversation ID (if None, list conversations).
            page_token: Optional page token.
            page_size: Page size.
            
        Returns:
            Paginated history.
        """
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        
        if conversation_id:
            # Get messages in conversation
            messages = self.service.get_messages(
                conversation_id=conversation_id,
                limit=limit,
                offset=offset,
            )
            
            items = [
                {
                    "id": msg.id,
                    "conversation_id": msg.conversation_id,
                    "role": msg.role,
                    "content": msg.content,
                    "model_ref": msg.model_ref,
                    "tokens_prompt": msg.tokens_prompt,
                    "tokens_completion": msg.tokens_completion,
                    "finish_reason": msg.finish_reason,
                    "run_id": msg.run_id,
                    "created_by": msg.created_by,
                    "metadata": msg.metadata_json,
                    "created_at": msg.created_at.isoformat() if msg.created_at else None,
                }
                for msg in messages
            ]
            
            has_next = len(messages) == limit
            next_offset = offset + len(messages) if has_next else None
            
            return PaginatedResponse.create(
                items=items,
                page_size=len(items),
                has_next=has_next,
                next_offset=next_offset,
            )
        else:
            # List conversations
            conversations = self.service.list_conversations(
                limit=limit,
                offset=offset,
            )
            
            items = [
                {
                    "id": conv.id,
                    "title": conv.title,
                    "status": conv.status,
                    "metadata": conv.metadata_json,
                    "system_prompt": conv.system_prompt,
                    "default_model_ref": conv.default_model_ref,
                    "default_temperature": conv.default_temperature,
                    "default_max_tokens": conv.default_max_tokens,
                    "default_top_p": conv.default_top_p,
                    "message_count": conv.message_count,
                    "last_message_at": conv.last_message_at.isoformat() if conv.last_message_at else None,
                    "created_by": conv.created_by,
                    "updated_by": conv.updated_by,
                    "created_at": conv.created_at.isoformat() if conv.created_at else None,
                    "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
                }
                for conv in conversations
            ]
            
            has_next = len(conversations) == limit
            next_offset = offset + len(conversations) if has_next else None
            
            return PaginatedResponse.create(
                items=items,
                page_size=len(items),
                has_next=has_next,
                next_offset=next_offset,
            )
    
    async def delete_conversation(
        self,
        ctx: RequestContext,
        conversation_id: str,
    ) -> None:
        """Delete conversation.
        
        Args:
            ctx: Request context.
            conversation_id: Conversation ID.
        """
        self.service.delete_conversation(conversation_id)

    async def create_conversation(
        self,
        ctx: RequestContext,
        data: ConversationCreate,
    ) -> ConversationResponse:
        """Create a new conversation.

        Args:
            ctx: Request context.
            data: Conversation creation data.

        Returns:
            Created conversation.
        """
        conversation = self.service.create_conversation(data)
        return ConversationResponse.model_validate(conversation)

    async def update_conversation(
        self,
        ctx: RequestContext,
        conversation_id: str,
        data: ConversationUpdate,
    ) -> ConversationResponse:
        """Update a conversation.

        Args:
            ctx: Request context.
            conversation_id: Conversation ID.
            data: Conversation update data.

        Returns:
            Updated conversation.
        """
        conversation = self.service.update_conversation(conversation_id, data)
        return ConversationResponse.model_validate(conversation)

    async def get_conversation(
        self,
        ctx: RequestContext,
        conversation_id: str,
    ) -> ConversationResponse:
        """Get conversation by ID.

        Args:
            ctx: Request context.
            conversation_id: Conversation ID.

        Returns:
            Conversation details.
        """
        conversation = self.service.get_conversation(conversation_id)
        return ConversationResponse.model_validate(conversation)

    async def list_conversations(
        self,
        ctx: RequestContext,
        page_token: Optional[str],
        page_size: int,
    ) -> PaginatedResponse[Dict[str, Any]]:
        """List conversations.

        Args:
            ctx: Request context.
            page_token: Optional page token.
            page_size: Page size.

        Returns:
            Paginated conversations.
        """
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        conversations = self.service.list_conversations(limit=limit, offset=offset)

        items = [serialize_conversation(conv) for conv in conversations]
        has_next = len(conversations) == limit
        next_offset = offset + len(conversations) if has_next else None

        return PaginatedResponse.create(
            items=items,
            page_size=len(items),
            has_next=has_next,
            next_offset=next_offset,
        )

    async def list_messages(
        self,
        ctx: RequestContext,
        conversation_id: str,
        page_token: Optional[str],
        page_size: int,
    ) -> PaginatedResponse[Dict[str, Any]]:
        """List messages in a conversation.

        Args:
            ctx: Request context.
            conversation_id: Conversation ID.
            page_token: Optional page token.
            page_size: Page size.

        Returns:
            Paginated messages.
        """
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0

        messages = self.service.get_messages(
            conversation_id=conversation_id,
            limit=limit,
            offset=offset,
        )

        items = [serialize_message(msg) for msg in messages]
        has_next = len(messages) == limit
        next_offset = offset + len(messages) if has_next else None

        return PaginatedResponse.create(
            items=items,
            page_size=len(items),
            has_next=has_next,
            next_offset=next_offset,
        )
