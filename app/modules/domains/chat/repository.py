""" repository

Chat domain repository.
"""

from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, desc

from app.kernel.db.repository import Repository
from app.kernel.contracts.context import RequestContext
from app.modules.domains.chat.models import Conversation, Message
from app.kernel.commons.errors import NotFoundError


class ConversationRepository(Repository[Conversation]):
    """Repository for Conversation model."""
    
    def __init__(self, db: Session, ctx: RequestContext):
        """Initialize conversation repository.
        
        Args:
            db: Database session.
            ctx: Request context.
        """
        super().__init__(Conversation, db, ctx)
    
    def create(self, conversation: Conversation) -> Conversation:
        """Create a new conversation.
        
        Args:
            conversation: Conversation instance.
            
        Returns:
            Created Conversation instance.
        """
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        return conversation
    
    def get_by_id(self, conversation_id: str) -> Optional[Conversation]:
        """Get conversation by ID.
        
        Args:
            conversation_id: Conversation ID.
            
        Returns:
            Conversation instance or None if not found.
        """
        query = select(Conversation).where(
            and_(
                Conversation.id == conversation_id,
                Conversation.tenant_id == self.ctx.tenant_id,
                Conversation.workspace_id == self.ctx.workspace_id,
                Conversation.deleted_at.is_(None),  # Exclude soft-deleted
            )
        )
        return self.db.exec(query).first()
    
    def list(
        self,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Conversation]:
        """List conversations.
        
        Args:
            limit: Maximum number of conversations.
            offset: Offset for pagination.
            
        Returns:
            List of Conversation instances.
        """
        query = select(Conversation).where(
            and_(
                Conversation.tenant_id == self.ctx.tenant_id,
                Conversation.workspace_id == self.ctx.workspace_id,
                Conversation.deleted_at.is_(None),  # Exclude soft-deleted
            )
        ).order_by(desc(Conversation.updated_at)).offset(offset).limit(limit)
        
        return list(self.db.exec(query).all())
    
    def soft_delete(self, conversation_id: str) -> Conversation:
        """Soft delete a conversation.
        
        Args:
            conversation_id: Conversation ID.
            
        Returns:
            Updated Conversation instance.
            
        Raises:
            NotFoundError: If conversation not found.
        """
        conversation = self.get_by_id(conversation_id)
        if not conversation:
            raise NotFoundError(f"Conversation not found: {conversation_id}")
        
        from app.kernel.commons.time import utc_now
        conversation.deleted_at = utc_now()
        conversation.updated_at = utc_now()
        
        self.db.commit()
        self.db.refresh(conversation)
        return conversation


class MessageRepository(Repository[Message]):
    """Repository for Message model."""
    
    def __init__(self, db: Session, ctx: RequestContext):
        """Initialize message repository.
        
        Args:
            db: Database session.
            ctx: Request context.
        """
        super().__init__(Message, db, ctx)
    
    def create(self, message: Message) -> Message:
        """Create a new message.
        
        Args:
            message: Message instance.
            
        Returns:
            Created Message instance.
        """
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message
    
    def list_by_conversation(
        self,
        conversation_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Message]:
        """List messages in a conversation.
        
        Args:
            conversation_id: Conversation ID.
            limit: Maximum number of messages.
            offset: Offset for pagination.
            
        Returns:
            List of Message instances.
        """
        query = select(Message).where(
            and_(
                Message.conversation_id == conversation_id,
                Message.tenant_id == self.ctx.tenant_id,
                Message.workspace_id == self.ctx.workspace_id,
            )
        ).order_by(Message.created_at).offset(offset).limit(limit)
        
        return list(self.db.exec(query).all())
    
    def count_by_conversation(self, conversation_id: str) -> int:
        """Count messages in a conversation.
        
        Args:
            conversation_id: Conversation ID.
            
        Returns:
            Number of messages.
        """
        from sqlalchemy import func
        query = select(func.count(Message.id)).where(
            and_(
                Message.conversation_id == conversation_id,
                Message.tenant_id == self.ctx.tenant_id,
                Message.workspace_id == self.ctx.workspace_id,
            )
        )
        result = self.db.exec(query).first()
        return result or 0

