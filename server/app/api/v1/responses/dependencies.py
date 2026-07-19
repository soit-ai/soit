"""Dependencies for Responses resource/projection endpoints."""

from collections.abc import AsyncIterator
from typing import Annotated, Protocol

from fastapi import Depends
from sqlalchemy.orm import Session

from app.infra.db.session import get_db
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.responses.interaction import InteractionProtocolAdapter
from app.kernel.runtime.responses.orchestrator import ResponseProjectionCoordinator
from app.kernel.runtime.responses.schemas import ResponseCreateRequest
from app.kernel.runtime.responses.service import ResponseService
from app.middleware.auth import get_current_context
from app.wiring.services import (
    build_response_projection_coordinator,
    build_response_service,
)


class ResponseInteractionExecutor(Protocol):
    """Execute one interaction using a session detached from its SSE request."""

    def __call__(
        self,
        payload: ResponseCreateRequest,
        *,
        interaction_id: str,
        parent_interaction_id: str | None,
        protocol: InteractionProtocolAdapter,
    ) -> AsyncIterator[dict]: ...


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


def get_response_interaction_executor(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[Session, Depends(get_db)],
) -> ResponseInteractionExecutor:
    """Build direct interactions on a worker session independent from SSE."""

    from sqlmodel import Session as SQLModelSession

    bind = db.get_bind()

    async def execute(
        payload: ResponseCreateRequest,
        *,
        interaction_id: str,
        parent_interaction_id: str | None,
        protocol: InteractionProtocolAdapter,
    ) -> AsyncIterator[dict]:
        with SQLModelSession(bind=bind, expire_on_commit=False) as worker_db:
            coordinator = build_response_projection_coordinator(db=worker_db, ctx=ctx)
            try:
                async for item in coordinator.execute_interaction_stream(
                    payload,
                    interaction_id=interaction_id,
                    parent_interaction_id=parent_interaction_id,
                    protocol=protocol,
                ):
                    yield item
            finally:
                worker_db.commit()

    return execute
