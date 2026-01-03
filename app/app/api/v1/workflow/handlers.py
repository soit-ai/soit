""" handlers

Workflow request handlers (thin orchestration).
"""

from typing import List, Optional
from fastapi import HTTPException, status

from app.kernel.contracts.context import RequestContext
from app.modules.workflow.application.service import WorkflowService
from app.modules.workflow.application.schemas import (
    WorkflowCreate,
    WorkflowUpdate,
    WorkflowResponse,
    WorkflowVersionResponse,
)
from app.infra.db.pagination import PaginatedResponse, parse_page_params, PageToken


class WorkflowHandlers:
    """Handlers for workflow API endpoints."""
    
    def __init__(self, service: WorkflowService):
        """Initialize workflow handlers.
        
        Args:
            service: WorkflowService instance.
        """
        self.service = service
    
    async def create_workflow(
        self,
        ctx: RequestContext,
        workflow_in: WorkflowCreate,
    ) -> WorkflowResponse:
        """Create a new workflow.
        
        Args:
            ctx: Request context.
            workflow_in: Workflow creation schema.
            
        Returns:
            Created workflow.
        """
        workflow = self.service.create_workflow(workflow_in)
        return WorkflowResponse.model_validate(workflow)
    
    async def list_workflows(
        self,
        ctx: RequestContext,
        page_token: Optional[str] = None,
        page_size: int = 20,
    ) -> PaginatedResponse[WorkflowResponse]:
        """List workflows.
        
        Args:
            ctx: Request context.
            page_token: Optional page token.
            page_size: Page size.
            
        Returns:
            Paginated workflows.
        """
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        
        workflows = self.service.list_workflows(limit=limit + 1, offset=offset)  # Fetch one extra to check has_next
        
        # Check if there are more workflows
        has_next = len(workflows) > limit
        if has_next:
            workflows = workflows[:limit]  # Remove the extra item
        
        # Convert items to WorkflowResponse
        items = [WorkflowResponse.model_validate(wf) for wf in workflows]
        
        next_offset = offset + len(items) if has_next else None
        
        return PaginatedResponse.create(
            items=items,
            page_size=len(items),
            has_next=has_next,
            next_offset=next_offset,
        )
    
    async def get_workflow(
        self,
        ctx: RequestContext,
        workflow_id: str,
    ) -> WorkflowResponse:
        """Get workflow by ID.
        
        Args:
            ctx: Request context.
            workflow_id: Workflow ID.
            
        Returns:
            Workflow details.
        """
        workflow = self.service.get_workflow(workflow_id)
        return WorkflowResponse.model_validate(workflow)
    
    async def update_workflow(
        self,
        ctx: RequestContext,
        workflow_id: str,
        workflow_in: WorkflowUpdate,
    ) -> WorkflowResponse:
        """Update workflow.
        
        Args:
            ctx: Request context.
            workflow_id: Workflow ID.
            workflow_in: Workflow update schema.
            
        Returns:
            Updated workflow.
        """
        workflow = self.service.update_workflow(workflow_id, workflow_in)
        return WorkflowResponse.model_validate(workflow)
    
    async def delete_workflow(
        self,
        ctx: RequestContext,
        workflow_id: str,
    ) -> None:
        """Delete workflow.
        
        Args:
            ctx: Request context.
            workflow_id: Workflow ID.
        """
        self.service.delete_workflow(workflow_id)
    
    async def publish_version(
        self,
        ctx: RequestContext,
        workflow_id: str,
        version_id: str,
    ) -> WorkflowResponse:
        """Publish workflow version.
        
        Args:
            ctx: Request context.
            workflow_id: Workflow ID.
            version_id: Version ID.
            
        Returns:
            Updated workflow.
        """
        # Rollback to specific version (which publishes it)
        workflow = self.service.rollback_version(workflow_id, version_id)
        return WorkflowResponse.model_validate(workflow)
    
    async def execute_workflow(
        self,
        ctx: RequestContext,
        workflow_id: str,
        inputs: dict,
    ) -> dict:
        """Execute workflow.
        
        Args:
            ctx: Request context.
            workflow_id: Workflow ID.
            inputs: Workflow inputs.
            
        Returns:
            Execution result.
        """
        result = await self.service.execute_workflow(workflow_id, inputs)
        return result

