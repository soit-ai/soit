"""Owner-only live diagnostics route."""

from fastapi import APIRouter, Depends

from app.api.v1.diagnostics.dependencies import get_diagnostics_service
from app.api.v1.permissions import require_workspace_owner_ctx
from app.kernel.contracts.context import RequestContext
from app.modules.diagnostics.application.schemas import DiagnosticsSnapshot
from app.modules.diagnostics.application.service import DiagnosticsService

router = APIRouter()


@router.get("", response_model=DiagnosticsSnapshot)
async def get_diagnostics_snapshot(
    _ctx: RequestContext = Depends(require_workspace_owner_ctx),
    service: DiagnosticsService = Depends(get_diagnostics_service),
) -> DiagnosticsSnapshot:
    return await service.snapshot()
