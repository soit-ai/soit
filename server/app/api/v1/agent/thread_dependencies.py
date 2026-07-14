"""Dependencies for agent thread APIs."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.infra.db.session import get_db
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.threads.service import ThreadService
from app.middleware.auth import get_current_context
from app.modules.agent.application.thread_query_service import AgentThreadQueryService


def get_thread_query_service(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[Session, Depends(get_db)],
) -> AgentThreadQueryService:
    """Resolve agent thread query service."""

    return AgentThreadQueryService(db=db, ctx=ctx)


def get_thread_runtime_service(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[Session, Depends(get_db)],
) -> ThreadService:
    """Resolve runtime thread write service."""

    return ThreadService(db=db, ctx=ctx)
