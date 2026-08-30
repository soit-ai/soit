"""Schedule API routes."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.v1.permissions import (
    require_workspace_read_ctx,
    require_workspace_write_ctx,
)
from app.api.v1.schedule.dependencies import get_schedule_service
from app.kernel.commons.errors import NotFoundError, ValidationError
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.schedules.schemas import (
    ScheduleCreate,
    SchedulePreviewRequest,
    SchedulePreviewResponse,
    ScheduleResponse,
    ScheduleUpdate,
)
from app.kernel.runtime.schedules.service import ScheduleService

router = APIRouter()


@router.get("", response_model=list[ScheduleResponse])
async def list_schedules(
    enabled: bool | None = None,
    limit: int = 100,
    offset: int = 0,
    _ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: ScheduleService = Depends(get_schedule_service),
):
    """List the workspace's schedules."""
    return [
        ScheduleResponse.model_validate(row)
        for row in service.list(enabled=enabled, limit=limit, offset=offset)
    ]


@router.post("/preview", response_model=SchedulePreviewResponse)
async def preview_schedule(
    payload: SchedulePreviewRequest,
    _ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: ScheduleService = Depends(get_schedule_service),
):
    """Show the next few firings for an expression, before it is saved."""
    try:
        return SchedulePreviewResponse(
            fires_at=service.preview(payload.cron, payload.timezone, count=payload.count)
        )
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    payload: ScheduleCreate,
    _ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: ScheduleService = Depends(get_schedule_service),
):
    """Create a schedule. An expression that cannot fire is refused here."""
    try:
        return ScheduleResponse.model_validate(
            service.create(
                name=payload.name,
                target_kind=payload.target_kind,
                target_id=payload.target_id,
                cron=payload.cron,
                timezone=payload.timezone,
                description=payload.description,
                inputs=payload.inputs,
                enabled=payload.enabled,
                catch_up=payload.catch_up,
            )
        )
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(
    schedule_id: str,
    _ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: ScheduleService = Depends(get_schedule_service),
):
    """Read one schedule."""
    try:
        return ScheduleResponse.model_validate(service.get(schedule_id))
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.patch("/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: str,
    payload: ScheduleUpdate,
    _ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: ScheduleService = Depends(get_schedule_service),
):
    """Change a schedule. Pausing or editing it recomputes the next firing."""
    try:
        return ScheduleResponse.model_validate(
            service.update(
                schedule_id,
                name=payload.name,
                description=payload.description,
                cron=payload.cron,
                timezone=payload.timezone,
                inputs=payload.inputs,
                enabled=payload.enabled,
                catch_up=payload.catch_up,
            )
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    schedule_id: str,
    _ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: ScheduleService = Depends(get_schedule_service),
):
    """Delete a schedule."""
    try:
        service.delete(schedule_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/{schedule_id}/run", response_model=ScheduleResponse)
async def run_schedule_now(
    schedule_id: str,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: ScheduleService = Depends(get_schedule_service),
):
    """Fire a schedule now, without waiting for its next occurrence.

    The manual firing goes through the same path the scheduler uses, so a test
    run behaves exactly like the real thing rather than proving a second code
    path works.
    """
    from app.wiring.schedule_worker import ScheduleWorker

    try:
        schedule = service.get(schedule_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    worker = ScheduleWorker(lambda: service.db, worker_id=f"manual:{ctx.user_id}")
    # advance=False: asking for a run now is not the same as moving the
    # schedule, so the next occurrence stays where it was.
    await worker.fire_schedule(schedule, db=service.db, advance=False)
    return ScheduleResponse.model_validate(service.get(schedule_id))
