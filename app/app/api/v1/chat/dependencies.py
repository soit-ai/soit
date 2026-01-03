""" dependencies

Chat entry dependencies (ctx/auth/policy).
"""

from typing import Annotated
from fastapi import Depends
from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.infra.db.session import get_db
from app.middleware.auth import get_current_context
from app.modules.chat.application.service import ChatService
from app.wiring.services import build_chat_service


def get_chat_service(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[Session, Depends(get_db)],
) -> ChatService:
    """Get chat service instance."""
    return build_chat_service(db=db, ctx=ctx)
