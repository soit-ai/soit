""" handlers

Chat request handlers (thin orchestration).
"""

from typing import Optional, AsyncGenerator, Dict, Any, Iterable, Tuple
from datetime import datetime
import asyncio
import base64
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
from app.infra.db.pagination import PaginatedResponse
from app.api.v1.schemas.chat import serialize_conversation, serialize_message


class ChatHandlers:
    """Handlers for chat API endpoints."""
    
    def __init__(self, service: ChatService):
        """Initialize chat handlers.
        
        Args:
            service: ChatService instance.
        """
        self.service = service

    def _clamp_page_size(self, page_size: int, max_page_size: int = 100) -> int:
        """Clamp page size to a safe range."""
        return min(max(1, page_size), max_page_size)

    def _decode_page_token(self, token_str: str) -> Optional[Dict[str, Any]]:
        """Decode a base64 or JSON page token."""
        if not token_str:
            return None
        try:
            decoded = base64.b64decode(token_str).decode("utf-8")
            return json.loads(decoded)
        except Exception:
            try:
                return json.loads(token_str)
            except Exception:
                return None

    def _parse_cursor_token(
        self,
        page_token: Optional[str],
        page_size: int,
        scope: str,
    ) -> Tuple[int, Optional[datetime], Optional[str], int]:
        """Parse cursor-based or legacy offset pagination token."""
        limit = self._clamp_page_size(page_size)
        cursor_at = None
        cursor_id = None
        offset = 0

        data = self._decode_page_token(page_token or "")
        if not data:
            return limit, cursor_at, cursor_id, offset

        token_scope = data.get("scope")
        if token_scope and token_scope != scope:
            return limit, cursor_at, cursor_id, offset

        if "cursor_at" in data and "cursor_id" in data:
            cursor_at_raw = data.get("cursor_at")
            cursor_id_val = data.get("cursor_id")
            try:
                if cursor_at_raw and cursor_id_val:
                    cursor_at = datetime.fromisoformat(cursor_at_raw)
                    cursor_id = str(cursor_id_val)
                    limit = self._clamp_page_size(int(data.get("limit", limit)))
                    return limit, cursor_at, cursor_id, 0
            except (TypeError, ValueError):
                cursor_at = None
                cursor_id = None

        if "offset" in data:
            try:
                offset = max(int(data.get("offset", 0)), 0)
                limit = self._clamp_page_size(int(data.get("limit", limit)))
            except (TypeError, ValueError):
                offset = 0

        return limit, cursor_at, cursor_id, offset

    def _encode_cursor_token(
        self,
        scope: str,
        limit: int,
        cursor_at: Optional[datetime],
        cursor_id: Optional[str],
    ) -> Optional[str]:
        """Encode cursor pagination token."""
        if not cursor_at or not cursor_id:
            return None
        payload = {
            "scope": scope,
            "limit": limit,
            "cursor_at": cursor_at.isoformat(),
            "cursor_id": cursor_id,
        }
        encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
        return base64.b64encode(encoded.encode("utf-8")).decode("utf-8")

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
        idempotency_key: Optional[str] = None,
    ) -> ChatCompletionResponse:
        """Create chat completion.
        
        Args:
            ctx: Request context.
            data: Chat completion request.
            
        Returns:
            Completion result.
        """
        result = await self.service.create_completion(data, idempotency_key=idempotency_key)
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
        idempotency_key: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream chat completion (SSE).
        
        Args:
            ctx: Request context.
            data: Chat completion request.
            
        Yields:
            SSE formatted data chunks.
        """
        try:
            async for event in self.service.stream_completion(data, idempotency_key=idempotency_key):
                event_type = event.get("type")
                if event_type == "start":
                    payload = {
                        "run_id": event["run_id"],
                        "conversation_id": event["conversation_id"],
                        "request_id": ctx.request_id,
                    }
                    yield f"event: start\ndata: {json.dumps(payload)}\n\n"
                    continue
                if event_type == "delta":
                    delta = event.get("delta") or ""
                    run_id = event.get("run_id")
                    chunk_size = data.stream_chunk_size or 80
                    for chunk in self._chunk_text(delta, chunk_size=chunk_size):
                        payload = {"delta": chunk}
                        if run_id:
                            payload["run_id"] = run_id
                        yield f"event: delta\ndata: {json.dumps(payload)}\n\n"
                    continue
                if event_type == "complete":
                    message = event["message"]
                    payload = {
                        "run_id": event["run_id"],
                        "message_id": message.id,
                        "model": event["model"],
                        "tokens_prompt": event["tokens_prompt"],
                        "tokens_completion": event["tokens_completion"],
                        "finish_reason": event["finish_reason"],
                    }
                    payload["metadata"] = message.metadata_json or {}
                    yield f"event: complete\ndata: {json.dumps(payload)}\n\n"
                    continue
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            payload = {
                "error": str(exc),
                "request_id": ctx.request_id,
            }
            yield f"event: error\ndata: {json.dumps(payload)}\n\n"
            return
    
    async def get_history(
        self,
        ctx: RequestContext,
        conversation_id: Optional[str] = None,
        page_token: Optional[str] = None,
        page_size: int = 20,
        status: Optional[str] = None,
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
        limit, cursor_at, cursor_id, offset = self._parse_cursor_token(
            page_token,
            page_size,
            scope="messages" if conversation_id else "conversations",
        )
        limit_plus = limit + 1
        
        if conversation_id:
            # Get messages in conversation
            messages = await self.service.get_messages(
                conversation_id=conversation_id,
                limit=limit_plus,
                offset=offset,
                cursor_at=cursor_at,
                cursor_id=cursor_id,
            )
            
            has_next = len(messages) > limit
            messages = messages[:limit]
            items = [
                {
                    "id": msg.id,
                    "conversation_id": msg.conversation_id,
                    "parent_id": msg.parent_id,
                    "role": msg.role,
                    "content": msg.content,
                    "model_ref": msg.model_ref,
                    "tokens_prompt": msg.tokens_prompt,
                    "tokens_completion": msg.tokens_completion,
                    "finish_reason": msg.finish_reason,
                    "run_id": msg.run_id,
                    "created_by": msg.created_by,
                    "metadata_json": msg.metadata_json,
                    "created_at": msg.created_at.isoformat() if msg.created_at else None,
                }
                for msg in messages
            ]

            next_token = None
            if has_next and messages:
                last = messages[-1]
                next_token = self._encode_cursor_token(
                    "messages",
                    limit,
                    last.created_at,
                    last.id,
                )

            return PaginatedResponse(
                items=items,
                next_page_token=next_token,
                page_size=len(items),
            )
        else:
            # List conversations
            conversations = await self.service.list_conversations(
                limit=limit_plus,
                offset=offset,
                cursor_at=cursor_at,
                cursor_id=cursor_id,
                status=status,
            )
            
            has_next = len(conversations) > limit
            conversations = conversations[:limit]
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

            next_token = None
            if has_next and conversations:
                last = conversations[-1]
                next_token = self._encode_cursor_token(
                    "conversations",
                    limit,
                    last.updated_at,
                    last.id,
                )

            return PaginatedResponse(
                items=items,
                next_page_token=next_token,
                page_size=len(items),
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
        await self.service.delete_conversation(conversation_id)

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
        conversation = await self.service.create_conversation(data)
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
        conversation = await self.service.update_conversation(conversation_id, data)
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
        conversation = await self.service.get_conversation(conversation_id)
        return ConversationResponse.model_validate(conversation)

    async def list_conversations(
        self,
        ctx: RequestContext,
        page_token: Optional[str],
        page_size: int,
        status: Optional[str] = None,
    ) -> PaginatedResponse[Dict[str, Any]]:
        """List conversations.

        Args:
            ctx: Request context.
            page_token: Optional page token.
            page_size: Page size.

        Returns:
            Paginated conversations.
        """
        limit, cursor_at, cursor_id, offset = self._parse_cursor_token(
            page_token,
            page_size,
            scope="conversations",
        )
        limit_plus = limit + 1
        conversations = await self.service.list_conversations(
            limit=limit_plus,
            offset=offset,
            cursor_at=cursor_at,
            cursor_id=cursor_id,
            status=status,
        )

        has_next = len(conversations) > limit
        conversations = conversations[:limit]
        items = [serialize_conversation(conv) for conv in conversations]
        next_token = None
        if has_next and conversations:
            last = conversations[-1]
            next_token = self._encode_cursor_token(
                "conversations",
                limit,
                last.updated_at,
                last.id,
            )

        return PaginatedResponse(
            items=items,
            next_page_token=next_token,
            page_size=len(items),
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
        limit, cursor_at, cursor_id, offset = self._parse_cursor_token(
            page_token,
            page_size,
            scope="messages",
        )
        limit_plus = limit + 1

        messages = await self.service.get_messages(
            conversation_id=conversation_id,
            limit=limit_plus,
            offset=offset,
            cursor_at=cursor_at,
            cursor_id=cursor_id,
        )

        has_next = len(messages) > limit
        messages = messages[:limit]
        items = [serialize_message(msg) for msg in messages]
        next_token = None
        if has_next and messages:
            last = messages[-1]
            next_token = self._encode_cursor_token(
                "messages",
                limit,
                last.created_at,
                last.id,
            )

        return PaginatedResponse(
            items=items,
            next_page_token=next_token,
            page_size=len(items),
        )
