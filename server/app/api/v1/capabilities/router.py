"""Runtime capability registry routes."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.permissions import require_workspace_read_ctx
from app.infra.db.pagination import PaginatedResponse
from app.infra.db.session import get_db
from app.kernel.contracts.context import RequestContext
from app.modules.capability_registry.application.schemas import CapabilityResponse
from app.modules.capability_registry.application.service import CapabilityRegistryService
from app.api.v1.capabilities.handlers import CapabilityRegistryHandlers


router = APIRouter()


@router.get("", response_model=PaginatedResponse[CapabilityResponse])
async def list_capabilities(
    kind: Optional[str] = None,
    source_kind: Optional[str] = None,
    page_token: Optional[str] = None,
    page_size: int = 200,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    db: Session = Depends(get_db),
):
    handlers = CapabilityRegistryHandlers(CapabilityRegistryService(db=db, ctx=ctx))
    return await handlers.list_capabilities(
        ctx,
        kind=kind,
        source_kind=source_kind,
        page_token=page_token,
        page_size=page_size,
    )
