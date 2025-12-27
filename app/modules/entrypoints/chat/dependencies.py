""" dependencies

Chat entry dependencies (ctx/auth/policy).
"""

from typing import Annotated
from fastapi import Depends
from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.kernel.db.session import get_db
from app.middleware.auth import get_current_context
from app.modules.domains.chat.service import ChatService


def get_chat_service(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[Session, Depends(get_db)],
) -> ChatService:
    """Get chat service instance.
    
    Args:
        ctx: Request context.
        db: Database session.
        
    Returns:
        ChatService instance.
    """
    return ChatService(db, ctx)
