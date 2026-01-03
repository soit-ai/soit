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
from app.modules.chat.infrastructure.repository import ConversationRepository, MessageRepository


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
    conversation_repo = ConversationRepository(db, ctx)
    message_repo = MessageRepository(db, ctx)
    return ChatService(db, ctx, conversation_repo, message_repo)
