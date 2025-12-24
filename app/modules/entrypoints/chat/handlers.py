""" handlers

Chat request handlers (thin orchestration).
"""

from typing import List, Optional, AsyncGenerator
from fastapi import HTTPException, status

from app.kernel.contracts.context import RequestContext
from app.modules.domains.workflow.service import WorkflowService


class ChatHandlers:
    """Handlers for chat API endpoints."""
    
    def __init__(self, workflow_service: WorkflowService):
        """Initialize chat handlers.
        
        Args:
            workflow_service: WorkflowService instance for executing chat workflows.
        """
        self.workflow_service = workflow_service
    
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
        limit: int = 20,
        offset: int = 0,
    ) -> List[dict]:
        """Get chat history.
        
        Args:
            ctx: Request context.
            conversation_id: Optional conversation ID.
            limit: Maximum number of messages.
            offset: Offset for pagination.
            
        Returns:
            List of chat messages.
        """
        # TODO: Implement chat history retrieval
        # This would typically query a conversation/message table
        return []
    
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
        # TODO: Implement conversation deletion
        pass
