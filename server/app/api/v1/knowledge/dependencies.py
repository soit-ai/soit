"""Dependencies for knowledge APIs."""

from typing import Annotated

from fastapi import Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.infra.db.session import get_async_db
from app.kernel.contracts.context import RequestContext
from app.middleware.auth import get_current_context
from app.modules.knowledge.application.service import KnowledgeService
from app.wiring.services import build_knowledge_reader_service, build_knowledge_service


def get_knowledge_service(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> KnowledgeService:
    """Resolve the knowledge application service."""

    return build_knowledge_service(db=db, ctx=ctx)


async def get_knowledge_reader_service(
    knowledge_id: str,
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> KnowledgeService:
    """The service for reading one knowledge base, which may be shared from
    another workspace of the tenant."""

    return await build_knowledge_reader_service(db=db, ctx=ctx, knowledge_id=knowledge_id)
