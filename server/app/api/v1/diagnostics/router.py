"""Owner-only live diagnostics route."""

from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.diagnostics.dependencies import get_diagnostics_service
from app.api.v1.permissions import require_tenant_admin_ctx, require_workspace_owner_ctx
from app.infra.db.session import get_async_db
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


@router.get("/telemetry")
async def get_telemetry_preview(
    _ctx: RequestContext = Depends(require_tenant_admin_ctx),
    db: AsyncSession = Depends(get_async_db),
) -> dict[str, Any]:
    """Whether anonymous telemetry is on, and the exact report the next daily send would carry."""
    from app.settings.settings import settings
    from app.wiring.telemetry import preview_report

    return await preview_report(settings, db)
