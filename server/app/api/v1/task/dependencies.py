"""Dependencies for runtime task APIs."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.infra.db.session import get_db
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.core.service import RuntimeCoreService
from app.kernel.runtime.query_service import RuntimeQueryService
from app.middleware.auth import get_current_context


def get_task_service(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[Session, Depends(get_db)],
) -> RuntimeQueryService:
    """Resolve runtime task query service."""

    return RuntimeQueryService(db=db, ctx=ctx)


def get_task_runtime_service(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[Session, Depends(get_db)],
) -> RuntimeCoreService:
    """Resolve runtime task write service."""

    return RuntimeCoreService(db=db, ctx=ctx)
