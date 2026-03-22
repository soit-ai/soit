""" dependencies

Memory entry dependencies.
"""

from typing import Annotated
from fastapi import Depends
from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.infra.db.session import get_db
from app.middleware.auth import get_current_context
from app.modules.memory.application.service import MemoryService
from app.wiring.services import build_memory_service


def get_memory_service(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[Session, Depends(get_db)],
) -> MemoryService:
    """Get memory service instance."""
    return build_memory_service(db=db, ctx=ctx)
