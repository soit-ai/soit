""" router

Workflow API routes (FastAPI).
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.kernel.db.session import get_db
from app.kernel.db.pagination import PaginatedResponse
from app.middleware.auth import get_current_context
from app.modules.domains.workflow.service import WorkflowService
from app.modules.domains.workflow.schemas import (
    WorkflowCreate,
    WorkflowUpdate,
    WorkflowResponse,
    WorkflowVersionCreate,
    WorkflowVersionResponse,
)
from app.modules.entrypoints.workflow.dependencies import get_workflow_service
from app.modules.entrypoints.workflow.handlers import WorkflowHandlers


router = APIRouter()


@router.post("", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    workflow_in: WorkflowCreate,
    ctx: RequestContext = Depends(get_current_context),
    service: WorkflowService = Depends(get_workflow_service),
):
    """Create a new workflow.
    
    Args:
        workflow_in: Workflow creation data.
        ctx: Request context.
        service: WorkflowService instance.
        
    Returns:
        Created workflow.
    """
    handlers = WorkflowHandlers(service)
    return await handlers.create_workflow(ctx, workflow_in)


@router.get("", response_model=PaginatedResponse[WorkflowResponse])
async def list_workflows(
    page_token: Optional[str] = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(get_current_context),
    service: WorkflowService = Depends(get_workflow_service),
):
    """List workflows.
    
    Args:
        page_token: Optional page token.
        page_size: Page size.
        ctx: Request context.
        service: WorkflowService instance.
        
    Returns:
        Paginated workflows.
    """
    handlers = WorkflowHandlers(service)
    return await handlers.list_workflows(ctx, page_token=page_token, page_size=page_size)


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: str,
    ctx: RequestContext = Depends(get_current_context),
    service: WorkflowService = Depends(get_workflow_service),
):
    """Get workflow by ID.
    
    Args:
        workflow_id: Workflow ID.
        ctx: Request context.
        service: WorkflowService instance.
        
    Returns:
        Workflow details.
    """
    handlers = WorkflowHandlers(service)
    return await handlers.get_workflow(ctx, workflow_id)


@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: str,
    workflow_in: WorkflowUpdate,
    ctx: RequestContext = Depends(get_current_context),
    service: WorkflowService = Depends(get_workflow_service),
):
    """Update workflow.
    
    Args:
        workflow_id: Workflow ID.
        workflow_in: Workflow update data.
        ctx: Request context.
        service: WorkflowService instance.
        
    Returns:
        Updated workflow.
    """
    handlers = WorkflowHandlers(service)
    return await handlers.update_workflow(ctx, workflow_id, workflow_in)


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(
    workflow_id: str,
    ctx: RequestContext = Depends(get_current_context),
    service: WorkflowService = Depends(get_workflow_service),
):
    """Delete workflow.
    
    Args:
        workflow_id: Workflow ID.
        ctx: Request context.
        service: WorkflowService instance.
    """
    handlers = WorkflowHandlers(service)
    await handlers.delete_workflow(ctx, workflow_id)


@router.post("/{workflow_id}/versions", response_model=WorkflowVersionResponse, status_code=status.HTTP_201_CREATED)
async def create_version(
    workflow_id: str,
    version_in: WorkflowVersionCreate,
    ctx: RequestContext = Depends(get_current_context),
    service: WorkflowService = Depends(get_workflow_service),
):
    """Create a new workflow version.
    
    Args:
        workflow_id: Workflow ID.
        version_in: Version creation data.
        ctx: Request context.
        service: WorkflowService instance.
        
    Returns:
        Created version.
    """
    version = service.create_version(workflow_id, version_in)
    return WorkflowVersionResponse.model_validate(version)


@router.post("/{workflow_id}/publish", response_model=WorkflowResponse)
async def publish_version(
    workflow_id: str,
    version_id: str = Body(...),
    ctx: RequestContext = Depends(get_current_context),
    service: WorkflowService = Depends(get_workflow_service),
):
    """Publish workflow version.
    
    Args:
        workflow_id: Workflow ID.
        version_id: Version ID to publish.
        ctx: Request context.
        service: WorkflowService instance.
        
    Returns:
        Updated workflow.
    """
    handlers = WorkflowHandlers(service)
    return await handlers.publish_version(ctx, workflow_id, version_id)


@router.post("/{workflow_id}/execute", status_code=status.HTTP_200_OK)
async def execute_workflow(
    workflow_id: str,
    inputs: dict = Body(...),
    ctx: RequestContext = Depends(get_current_context),
    service: WorkflowService = Depends(get_workflow_service),
):
    """Execute workflow.
    
    Args:
        workflow_id: Workflow ID.
        inputs: Workflow inputs.
        ctx: Request context.
        service: WorkflowService instance.
        
    Returns:
        Execution result.
    """
    handlers = WorkflowHandlers(service)
    return await handlers.execute_workflow(ctx, workflow_id, inputs)


@router.get("/{workflow_id}/runs")
async def list_runs(
    workflow_id: str,
    page_token: Optional[str] = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(get_current_context),
    service: WorkflowService = Depends(get_workflow_service),
):
    """List workflow runs.
    
    Args:
        workflow_id: Workflow ID.
        page_token: Optional page token.
        page_size: Page size.
        ctx: Request context.
        service: WorkflowService instance.
        
    Returns:
        Paginated runs.
    """
    from app.kernel.db.pagination import parse_page_params
    
    # Parse pagination parameters
    limit, token_obj = parse_page_params(page_token, page_size)
    offset = token_obj.offset if token_obj else 0
    
    # Get runs
    runs = service.list_runs(workflow_id, limit=limit, offset=offset)
    
    # Check if there are more runs
    has_next = len(runs) == limit
    next_offset = offset + len(runs) if has_next else None
    
    # Create paginated response
    return PaginatedResponse.create(
        items=runs,
        page_size=len(runs),
        has_next=has_next,
        next_offset=next_offset,
    )


@router.get("/{workflow_id}/runs/{run_id}")
async def get_run(
    workflow_id: str,
    run_id: str,
    ctx: RequestContext = Depends(get_current_context),
    service: WorkflowService = Depends(get_workflow_service),
):
    """Get run details.
    
    Args:
        workflow_id: Workflow ID.
        run_id: Run ID.
        ctx: Request context.
        service: WorkflowService instance.
        
    Returns:
        Run details.
    """
    return service.get_run(workflow_id, run_id)

