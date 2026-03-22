"""Dependencies for runtime thread APIs."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.infra.db.session import get_db
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.core.service import RuntimeCoreService
from app.kernel.runtime.query_service import RuntimeQueryService
from app.middleware.auth import get_current_context


def get_thread_query_service(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[Session, Depends(get_db)],
) -> RuntimeQueryService:
    """Resolve runtime thread query service."""

    return RuntimeQueryService(db=db, ctx=ctx)


def get_thread_runtime_service(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[Session, Depends(get_db)],
) -> RuntimeCoreService:
    """Resolve runtime thread write service."""

    return RuntimeCoreService(db=db, ctx=ctx)
