""" handlers

Chat request handlers (thin orchestration).
"""

from typing import List, Optional, AsyncGenerator, Dict, Any
from fastapi import HTTPException, status
import json

from app.kernel.contracts.context import RequestContext
from app.modules.domains.chat.service import ChatService
from app.modules.domains.workflow.service import WorkflowService
from app.kernel.db.pagination import PaginatedResponse, parse_page_params


class ChatHandlers:
    """Handlers for chat API endpoints."""
    
    def __init__(self, service: ChatService, workflow_service: Optional[WorkflowService] = None):
        """Initialize chat handlers.
        
        Args:
            service: ChatService instance.
            workflow_service: Optional WorkflowService instance for executing workflows.
        """
        self.service = service
        self.workflow_service = workflow_service
    
    async def create_completion(
        self,
        ctx: RequestContext,
        workflow_id: str,
        messages: List[dict],
        stream: bool = False,
        workflow_service: Optional[WorkflowService] = None,
    ) -> dict:
        """Create chat completion.
        
        Args:
            ctx: Request context.
            workflow_id: Workflow ID to execute.
            messages: Chat messages.
            stream: Whether to stream the response.
            workflow_service: Optional WorkflowService instance.
            
        Returns:
            Completion result.
        """
        if not workflow_service and not self.workflow_service:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="WorkflowService not available"
            )
        
        ws = workflow_service or self.workflow_service
        
        # Prepare inputs for workflow execution
        inputs = {
            "messages": messages,
        }
        
        # Execute workflow
        result = await ws.execute_workflow(workflow_id, inputs)
        
        # Extract run_id from result if available, otherwise generate one
        from app.kernel.commons.ids import generate_ulid
        run_id = result.get("run_id") or generate_ulid()
        
        return {
            "run_id": run_id,
            "status": "completed",
            "result": result
        }
    
    async def stream_completion(
        self,
        ctx: RequestContext,
        workflow_id: str,
        messages: List[dict],
        workflow_service: Optional[WorkflowService] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream chat completion (SSE).
        
        Args:
            ctx: Request context.
            workflow_id: Workflow ID to execute.
            messages: Chat messages.
            workflow_service: Optional WorkflowService instance.
            
        Yields:
            SSE formatted data chunks.
        """
        if not workflow_service and not self.workflow_service:
            yield f"event: error\ndata: {json.dumps({'error': 'WorkflowService not available'})}\n\n"
            return
        
        ws = workflow_service or self.workflow_service
        
        # Use SSE handler for streaming
        from app.modules.entrypoints.sse.handlers import SSEHandlers
        import json
        
        sse_handlers = SSEHandlers(ws)
        inputs = {
            "messages": messages,
        }
        
        async for chunk in sse_handlers.stream_execution(ctx, workflow_id, inputs):
            yield chunk
    
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
