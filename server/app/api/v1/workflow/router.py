""" router

Workflow API routes (FastAPI).
"""


from json import JSONDecodeError

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.v1.permissions import (
    require_workspace_read_ctx,
    require_workspace_write_ctx,
)
from app.api.v1.workflow.dependencies import get_workflow_service
from app.api.v1.workflow.handlers import WorkflowHandlers
from app.api.v1.workflow.streaming import SSEHandlers
from app.infra.db.pagination import PaginatedResponse
from app.kernel.contracts.context import RequestContext
from app.modules.workflow.application.schemas import (
    WorkflowCapabilitiesResponse,
    WorkflowCreate,
    WorkflowDSLExport,
    WorkflowDSLImport,
    WorkflowPublishRequest,
    WorkflowReleaseResponse,
    WorkflowResponse,
    WorkflowRollbackRequest,
    WorkflowTemplateCreate,
    WorkflowUpdate,
    WorkflowVersionCreate,
    WorkflowVersionResponse,
    WorkflowWorkbenchItemsResponse,
    WorkflowWorkbenchResponse,
)
from app.modules.workflow.application.service import WorkflowService

router = APIRouter()


async def _reject_caller_supplied_actor(
    request: Request,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
) -> RequestContext:
    content_type = request.headers.get("content-type")
    if content_type is not None:
        media_type = content_type.split(";", 1)[0].strip().lower()
        if media_type != "application/json" and not media_type.endswith("+json"):
            return ctx
    try:
        payload = await request.json()
    except (JSONDecodeError, UnicodeDecodeError):
        return ctx
    if isinstance(payload, dict) and "created_by" in payload:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="created_by is resolved from the authenticated request context",
        )
    return ctx


class WorkflowStreamRequest(BaseModel):
    """Workflow stream request payload."""

    inputs: dict = Field(default_factory=dict)


@router.post("", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    workflow_in: WorkflowCreate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
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


@router.post("/templates/ticket-triage", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def create_ticket_triage_template(
    template_in: WorkflowTemplateCreate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: WorkflowService = Depends(get_workflow_service),
):
    """Create a ticket triage workflow draft from the built-in template."""
    handlers = WorkflowHandlers(service)
    return await handlers.create_ticket_triage_template(ctx, template_in)


@router.get("", response_model=PaginatedResponse[WorkflowResponse])
async def list_workflows(
    page_token: str | None = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
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


@router.get("/workbench", response_model=WorkflowWorkbenchResponse)
async def get_workflow_workbench(
    page_token: str | None = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: WorkflowService = Depends(get_workflow_service),
):
    """Get Workflow workbench aggregate data."""
    handlers = WorkflowHandlers(service)
    return await handlers.get_workbench(ctx, page_token=page_token, page_size=page_size)


@router.get("/workbench/items", response_model=WorkflowWorkbenchItemsResponse)
async def list_workflow_workbench_items(
    tab: str | None = None,
    keyword: str | None = None,
    page_token: str | None = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: WorkflowService = Depends(get_workflow_service),
):
    """Get Workflow workbench table rows."""
    handlers = WorkflowHandlers(service)
    return await handlers.get_workbench_items(
        ctx,
        page_token=page_token,
        page_size=page_size,
        tab=tab,
        keyword=keyword,
    )


@router.get("/capabilities", response_model=WorkflowCapabilitiesResponse)
async def get_workflow_capabilities(
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: WorkflowService = Depends(get_workflow_service),
):
    """Get backend-owned workflow node capabilities."""
    handlers = WorkflowHandlers(service)
    return await handlers.get_capabilities(ctx)


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
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


@router.get("/{workflow_id}/versions", response_model=PaginatedResponse[WorkflowVersionResponse])
async def list_versions(
    workflow_id: str,
    page_token: str | None = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: WorkflowService = Depends(get_workflow_service),
):
    """List workflow versions."""
    handlers = WorkflowHandlers(service)
    return await handlers.list_versions(ctx, workflow_id, page_token=page_token, page_size=page_size)


@router.get("/{workflow_id}/releases", response_model=PaginatedResponse[WorkflowReleaseResponse])
async def list_releases(
    workflow_id: str,
    page_token: str | None = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: WorkflowService = Depends(get_workflow_service),
):
    """List workflow release history."""
    handlers = WorkflowHandlers(service)
    return await handlers.list_releases(ctx, workflow_id, page_token=page_token, page_size=page_size)


@router.get("/{workflow_id}/version/current", response_model=WorkflowVersionResponse)
async def get_current_version(
    workflow_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: WorkflowService = Depends(get_workflow_service),
):
    """Get current workflow version."""
    handlers = WorkflowHandlers(service)
    return await handlers.get_current_version(ctx, workflow_id)


@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: str,
    workflow_in: WorkflowUpdate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
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
    ctx: RequestContext = Depends(require_workspace_write_ctx),
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


@router.post(
    "/{workflow_id}/versions",
    response_model=WorkflowVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_version(
    workflow_id: str,
    version_in: WorkflowVersionCreate,
    ctx: RequestContext = Depends(_reject_caller_supplied_actor),
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
    handlers = WorkflowHandlers(service)
    return await handlers.create_version(ctx, workflow_id, version_in)


@router.post("/{workflow_id}/publish", response_model=WorkflowResponse)
async def publish_version(
    workflow_id: str,
    payload: WorkflowPublishRequest,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: WorkflowService = Depends(get_workflow_service),
):
    """Publish workflow version.

    Args:
        workflow_id: Workflow ID.
        payload: Publish request payload.
        ctx: Request context.
        service: WorkflowService instance.

    Returns:
        Updated workflow.
    """
    handlers = WorkflowHandlers(service)
    return await handlers.publish_version(ctx, workflow_id, payload)


@router.post("/{workflow_id}/rollback", response_model=WorkflowResponse)
async def rollback_version(
    workflow_id: str,
    payload: WorkflowRollbackRequest,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: WorkflowService = Depends(get_workflow_service),
):
    """Rollback workflow version."""
    handlers = WorkflowHandlers(service)
    return await handlers.rollback_version(ctx, workflow_id, payload)


@router.post("/{workflow_id}/execute", status_code=status.HTTP_200_OK)
async def execute_workflow(
    workflow_id: str,
    inputs: dict = Body(...),
    ctx: RequestContext = Depends(require_workspace_write_ctx),
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


@router.post("/{workflow_id}/stream")
async def stream_workflow(
    workflow_id: str,
    payload: WorkflowStreamRequest,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: WorkflowService = Depends(get_workflow_service),
):
    """Stream workflow execution updates."""
    handlers = SSEHandlers(service)

    async def generate():
        async for chunk in handlers.stream_execution(ctx, workflow_id, payload.inputs):
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


@router.post("/{workflow_id}/runs/{run_id}/pause")
async def pause_run(
    workflow_id: str,
    run_id: str,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: WorkflowService = Depends(get_workflow_service),
):
    """Pause workflow run."""
    handlers = WorkflowHandlers(service)
    return await handlers.pause_run(ctx, workflow_id, run_id)


@router.post("/{workflow_id}/runs/{run_id}/resume")
async def resume_run(
    workflow_id: str,
    run_id: str,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: WorkflowService = Depends(get_workflow_service),
):
    """Resume workflow run."""
    handlers = WorkflowHandlers(service)
    return await handlers.resume_run(ctx, workflow_id, run_id)


@router.post("/{workflow_id}/runs/{run_id}/cancel")
async def cancel_run(
    workflow_id: str,
    run_id: str,
    payload: dict | None = Body(default=None),
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: WorkflowService = Depends(get_workflow_service),
):
    """Cancel workflow run."""
    handlers = WorkflowHandlers(service)
    return await handlers.cancel_run(ctx, workflow_id, run_id, payload)


@router.post("/{workflow_id}/runs/{run_id}/fail")
async def fail_run(
    workflow_id: str,
    run_id: str,
    payload: dict | None = Body(default=None),
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: WorkflowService = Depends(get_workflow_service),
):
    """Mark workflow run failed."""
    handlers = WorkflowHandlers(service)
    return await handlers.fail_run(ctx, workflow_id, run_id, payload)


@router.post("/{workflow_id}/runs/{run_id}/retry")
async def retry_run(
    workflow_id: str,
    run_id: str,
    inputs: dict | None = Body(default=None),
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: WorkflowService = Depends(get_workflow_service),
):
    """Retry workflow run."""
    handlers = WorkflowHandlers(service)
    return await handlers.retry_run(ctx, workflow_id, run_id, inputs)


@router.post("/{workflow_id}/runs/{run_id}/replay")
async def replay_run(
    workflow_id: str,
    run_id: str,
    inputs: dict | None = Body(default=None),
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: WorkflowService = Depends(get_workflow_service),
):
    """Replay workflow run."""
    handlers = WorkflowHandlers(service)
    return await handlers.replay_run(ctx, workflow_id, run_id, inputs)


@router.get("/{workflow_id}/dsl", response_model=WorkflowDSLExport)
async def export_dsl(
    workflow_id: str,
    version_id: str | None = None,
    format: str = "json",
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: WorkflowService = Depends(get_workflow_service),
):
    """Export workflow DSL."""
    handlers = WorkflowHandlers(service)
    return await handlers.export_dsl(ctx, workflow_id, version_id=version_id, format=format)


@router.post(
    "/{workflow_id}/dsl",
    response_model=WorkflowVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_dsl(
    workflow_id: str,
    dsl_in: WorkflowDSLImport,
    ctx: RequestContext = Depends(_reject_caller_supplied_actor),
    service: WorkflowService = Depends(get_workflow_service),
):
    """Import workflow DSL."""
    handlers = WorkflowHandlers(service)
    return await handlers.import_dsl(ctx, workflow_id, dsl_in)
