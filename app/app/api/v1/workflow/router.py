""" router

Workflow API routes (FastAPI).
"""

from typing import Optional
from fastapi import APIRouter, Depends, status, Body

from app.kernel.contracts.context import RequestContext
from app.infra.db.pagination import PaginatedResponse
from app.api.v1.permissions import (
    require_workspace_read_ctx,
    require_workspace_write_ctx,
)
from app.modules.workflow.application.app_facade import WorkflowAppFacadeService
from app.modules.workflow.application.schemas import (
    WorkflowCreate,
    WorkflowUpdate,
    WorkflowResponse,
    WorkflowVersionCreate,
    WorkflowVersionResponse,
    WorkflowDSLImport,
    WorkflowDSLExport,
    WorkflowPublishRequest,
)
from app.api.v1.workflow.dependencies import get_workflow_service
from app.api.v1.workflow.handlers import WorkflowHandlers


router = APIRouter()


@router.post("", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    workflow_in: WorkflowCreate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: WorkflowAppFacadeService = Depends(get_workflow_service),
):
    """Create a new workflow.
    
    Args:
        workflow_in: Workflow creation data.
        ctx: Request context.
        service: WorkflowAppFacadeService instance.
        
    Returns:
        Created workflow.
    """
    handlers = WorkflowHandlers(service)
    return await handlers.create_workflow(ctx, workflow_in)


@router.get("", response_model=PaginatedResponse[WorkflowResponse])
async def list_workflows(
    page_token: Optional[str] = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: WorkflowAppFacadeService = Depends(get_workflow_service),
):
    """List workflows.
    
    Args:
        page_token: Optional page token.
        page_size: Page size.
        ctx: Request context.
        service: WorkflowAppFacadeService instance.
        
    Returns:
        Paginated workflows.
    """
    handlers = WorkflowHandlers(service)
    return await handlers.list_workflows(ctx, page_token=page_token, page_size=page_size)


@router.get("/{app_id}", response_model=WorkflowResponse)
async def get_workflow(
    app_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: WorkflowAppFacadeService = Depends(get_workflow_service),
):
    """Get workflow by ID.
    
    Args:
        app_id: App ID.
        ctx: Request context.
        service: WorkflowAppFacadeService instance.
        
    Returns:
        Workflow details.
    """
    handlers = WorkflowHandlers(service)
    return await handlers.get_workflow(ctx, app_id)


@router.get("/{app_id}/versions", response_model=PaginatedResponse[WorkflowVersionResponse])
async def list_versions(
    app_id: str,
    page_token: Optional[str] = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: WorkflowAppFacadeService = Depends(get_workflow_service),
):
    """List workflow versions."""
    handlers = WorkflowHandlers(service)
    return await handlers.list_versions(ctx, app_id, page_token=page_token, page_size=page_size)


@router.get("/{app_id}/version/current", response_model=WorkflowVersionResponse)
async def get_current_version(
    app_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: WorkflowAppFacadeService = Depends(get_workflow_service),
):
    """Get current workflow version."""
    handlers = WorkflowHandlers(service)
    return await handlers.get_current_version(ctx, app_id)


@router.put("/{app_id}", response_model=WorkflowResponse)
async def update_workflow(
    app_id: str,
    workflow_in: WorkflowUpdate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: WorkflowAppFacadeService = Depends(get_workflow_service),
):
    """Update workflow.
    
    Args:
        app_id: App ID.
        workflow_in: Workflow update data.
        ctx: Request context.
        service: WorkflowAppFacadeService instance.
        
    Returns:
        Updated workflow.
    """
    handlers = WorkflowHandlers(service)
    return await handlers.update_workflow(ctx, app_id, workflow_in)


@router.delete("/{app_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(
    app_id: str,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: WorkflowAppFacadeService = Depends(get_workflow_service),
):
    """Delete workflow.
    
    Args:
        app_id: App ID.
        ctx: Request context.
        service: WorkflowAppFacadeService instance.
    """
    handlers = WorkflowHandlers(service)
    await handlers.delete_workflow(ctx, app_id)


@router.post("/{app_id}/versions", response_model=WorkflowVersionResponse, status_code=status.HTTP_201_CREATED)
async def create_version(
    app_id: str,
    version_in: WorkflowVersionCreate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: WorkflowAppFacadeService = Depends(get_workflow_service),
):
    """Create a new workflow version.
    
    Args:
        app_id: App ID.
        version_in: Version creation data.
        ctx: Request context.
        service: WorkflowAppFacadeService instance.
        
    Returns:
        Created version.
    """
    handlers = WorkflowHandlers(service)
    return await handlers.create_version(ctx, app_id, version_in)


@router.post("/{app_id}/publish", response_model=WorkflowResponse)
async def publish_version(
    app_id: str,
    payload: WorkflowPublishRequest,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: WorkflowAppFacadeService = Depends(get_workflow_service),
):
    """Publish workflow version.
    
    Args:
        app_id: App ID.
        payload: Publish request payload.
        ctx: Request context.
        service: WorkflowAppFacadeService instance.
        
    Returns:
        Updated workflow.
    """
    handlers = WorkflowHandlers(service)
    return await handlers.publish_version(ctx, app_id, payload.version_id, preflight=payload.preflight)


@router.post("/{app_id}/execute", status_code=status.HTTP_200_OK)
async def execute_workflow(
    app_id: str,
    inputs: dict = Body(...),
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: WorkflowAppFacadeService = Depends(get_workflow_service),
):
    """Execute workflow.
    
    Args:
        app_id: App ID.
        inputs: Workflow inputs.
        ctx: Request context.
        service: WorkflowAppFacadeService instance.
        
    Returns:
        Execution result.
    """
    handlers = WorkflowHandlers(service)
    return await handlers.execute_workflow(ctx, app_id, inputs)


@router.post("/{app_id}/runs/{run_id}/pause")
async def pause_run(
    app_id: str,
    run_id: str,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: WorkflowAppFacadeService = Depends(get_workflow_service),
):
    """Pause workflow run."""
    handlers = WorkflowHandlers(service)
    return await handlers.pause_run(ctx, app_id, run_id)


@router.post("/{app_id}/runs/{run_id}/resume")
async def resume_run(
    app_id: str,
    run_id: str,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: WorkflowAppFacadeService = Depends(get_workflow_service),
):
    """Resume workflow run."""
    handlers = WorkflowHandlers(service)
    return await handlers.resume_run(ctx, app_id, run_id)


@router.post("/{app_id}/runs/{run_id}/retry")
async def retry_run(
    app_id: str,
    run_id: str,
    inputs: Optional[dict] = Body(default=None),
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: WorkflowAppFacadeService = Depends(get_workflow_service),
):
    """Retry workflow run."""
    handlers = WorkflowHandlers(service)
    return await handlers.retry_run(ctx, app_id, run_id, inputs)


@router.post("/{app_id}/runs/{run_id}/replay")
async def replay_run(
    app_id: str,
    run_id: str,
    inputs: Optional[dict] = Body(default=None),
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: WorkflowAppFacadeService = Depends(get_workflow_service),
):
    """Replay workflow run."""
    handlers = WorkflowHandlers(service)
    return await handlers.replay_run(ctx, app_id, run_id, inputs)


@router.get("/{app_id}/dsl", response_model=WorkflowDSLExport)
async def export_dsl(
    app_id: str,
    version_id: Optional[str] = None,
    format: str = "json",
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: WorkflowAppFacadeService = Depends(get_workflow_service),
):
    """Export workflow DSL."""
    handlers = WorkflowHandlers(service)
    return await handlers.export_dsl(ctx, app_id, version_id=version_id, format=format)


@router.post("/{app_id}/dsl", response_model=WorkflowVersionResponse, status_code=status.HTTP_201_CREATED)
async def import_dsl(
    app_id: str,
    dsl_in: WorkflowDSLImport,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: WorkflowAppFacadeService = Depends(get_workflow_service),
):
    """Import workflow DSL."""
    handlers = WorkflowHandlers(service)
    return await handlers.import_dsl(ctx, app_id, dsl_in)
