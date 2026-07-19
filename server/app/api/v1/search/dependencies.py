"""Global search dependencies."""

from typing import Annotated

from fastapi import Depends
from sqlmodel import Session

from app.infra.db.session import get_db
from app.kernel.contracts.context import RequestContext
from app.middleware.auth import get_current_context
from app.modules.search.application.service import GlobalSearchService


def get_global_search_service(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[Session, Depends(get_db)],
) -> GlobalSearchService:
    return GlobalSearchService(db=db, ctx=ctx)
