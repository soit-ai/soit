""" handlers

Chat request handlers (thin orchestration).
"""

from typing import List, Optional, AsyncGenerator, Dict, Any
from fastapi import HTTPException, status

from app.kernel.contracts.context import RequestContext
from app.modules.domains.chat.service import ChatService
from app.kernel.db.pagination import PaginatedResponse, parse_page_params


class ChatHandlers:
    """Handlers for chat API endpoints."""
    
    def __init__(self, service: ChatService):
        """Initialize chat handlers.
        
        Args:
            service: ChatService instance.
        """
        self.service = service
    
    async def create_completion(
        self,
        ctx: RequestContext,
        workflow_id: str,
        messages: List[dict],
        stream: bool = False,
    ) -> dict:
        """Create chat completion.
        
        Args:
            ctx: Request context.
            workflow_id: Workflow ID to execute.
            messages: Chat messages.
            stream: Whether to stream the response.
            
        Returns:
            Completion result.
        """
        # Prepare inputs for workflow execution
        inputs = {
            "messages": messages,
        }
        
        # Execute workflow
        # TODO: Implement async workflow execution
        # For now, use compile_workflow and return a placeholder
        from app.kernel.commons.ids import generate_ulid
        run_id = generate_ulid()
        execution_plan = self.workflow_service.compile_workflow(workflow_id, inputs, run_id)
        return {"run_id": run_id, "status": "pending", "plan": str(execution_plan)}
    
    async def stream_completion(
        self,
        ctx: RequestContext,
        workflow_id: str,
        messages: List[dict],
    ) -> AsyncGenerator[str, None]:
        """Stream chat completion (SSE).
        
        Args:
            ctx: Request context.
            workflow_id: Workflow ID to execute.
            messages: Chat messages.
            
        Yields:
            SSE formatted data chunks.
        """
        # TODO: Implement streaming execution
        # For now, return a simple completion
        inputs = {
            "messages": messages,
        }
        from app.kernel.commons.ids import generate_ulid
        run_id = generate_ulid()
        execution_plan = self.workflow_service.compile_workflow(workflow_id, inputs, run_id)
        result = {"run_id": run_id, "status": "pending", "plan": str(execution_plan)}
        
        # Format as SSE
        yield f"data: {result}\n\n"
        yield "data: [DONE]\n\n"
    
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
                    "metadata": conv.metadata_json,
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
