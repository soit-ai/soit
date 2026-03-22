"""Dependencies for Responses resource/projection endpoints."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.infra.db.session import get_db
from app.kernel.contracts.context import RequestContext
from app.kernel.responses.orchestrator import ResponseOrchestrator, ResponseProjectionCoordinator
from app.kernel.responses.service import ResponseService
from app.middleware.auth import get_current_context
from app.wiring.services import build_response_orchestrator, build_response_projection_coordinator, build_response_service


def get_response_service(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[Session, Depends(get_db)],
) -> ResponseService:
    """Resolve the response resource/projection service."""

    return build_response_service(db=db, ctx=ctx)


def get_response_projection_coordinator(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[Session, Depends(get_db)],
) -> ResponseProjectionCoordinator:
    """Resolve the response semantic projection coordinator."""

    return build_response_projection_coordinator(db=db, ctx=ctx)


def get_response_orchestrator(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[Session, Depends(get_db)],
) -> ResponseOrchestrator:
    """Backward-compatible alias for the response projection coordinator."""

    return build_response_orchestrator(db=db, ctx=ctx)
