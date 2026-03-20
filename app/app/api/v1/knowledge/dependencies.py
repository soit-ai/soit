"""Dependencies for knowledge APIs."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.infra.db.session import get_db
from app.kernel.contracts.context import RequestContext
from app.middleware.auth import get_current_context
from app.modules.knowledge.application.service import KnowledgeService
from app.wiring.services import build_knowledge_service


def get_knowledge_service(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[Session, Depends(get_db)],
) -> KnowledgeService:
    """Resolve the knowledge application service."""

    return build_knowledge_service(db=db, ctx=ctx)
