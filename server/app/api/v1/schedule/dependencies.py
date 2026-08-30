"""Schedule API dependencies."""

from fastapi import Depends
from sqlmodel import Session

from app.api.v1.permissions import require_workspace_read_ctx
from app.infra.db.session import get_db
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.schedules.service import ScheduleService


def get_schedule_service(
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(require_workspace_read_ctx),
) -> ScheduleService:
    """Build a workspace-scoped schedule service."""
    return ScheduleService(db, ctx)
