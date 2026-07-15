"""Dependencies for runtime task APIs."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.infra.db.session import get_db
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.tasks.query_service import TaskQueryService
from app.kernel.runtime.tasks.service import TaskService
from app.middleware.auth import get_current_context


def get_task_service(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[Session, Depends(get_db)],
) -> TaskQueryService:
    """Resolve runtime task query service."""

    return TaskQueryService(db=db, ctx=ctx)


def get_task_runtime_service(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[Session, Depends(get_db)],
) -> TaskService:
    """Resolve runtime task write service."""

    return TaskService(db=db, ctx=ctx)
