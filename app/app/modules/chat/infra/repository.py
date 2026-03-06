""" repository

Chat domain repository.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, desc, or_

from app.infra.db.repository import Repository
from app.kernel.contracts.context import RequestContext
from app.modules.chat.domain.models import Conversation, Message
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
        result = self.db.exec(query).first()
        return self._unwrap_result(result)
    
    def list(
        self,
        limit: int = 20,
        offset: int = 0,
        cursor_at: Optional[datetime] = None,
        cursor_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Conversation]:
        """List conversations.
        
        Args:
            limit: Maximum number of conversations.
            offset: Offset for pagination.
            cursor_at: Updated_at cursor for pagination.
            cursor_id: Conversation ID cursor for pagination.
            
        Returns:
            List of Conversation instances.
        """
        query = select(Conversation).where(
            and_(
                Conversation.tenant_id == self.ctx.tenant_id,
                Conversation.workspace_id == self.ctx.workspace_id,
                Conversation.deleted_at.is_(None),  # Exclude soft-deleted
            )
        )
        if status:
            query = query.where(Conversation.status == status)

        if cursor_at and cursor_id:
            query = query.where(
                or_(
                    Conversation.updated_at < cursor_at,
                    and_(
                        Conversation.updated_at == cursor_at,
                        Conversation.id < cursor_id,
                    ),
                )
            )
        elif offset:
            query = query.offset(offset)

        query = query.order_by(desc(Conversation.updated_at), desc(Conversation.id)).limit(limit)
        
        results = list(self.db.exec(query).all())
        return self._unwrap_all(results)
    
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

    def update(
        self,
        conversation_id: str,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        status: Optional[str] = None,
        system_prompt: Optional[str] = None,
        default_model_ref: Optional[str] = None,
        default_temperature: Optional[float] = None,
        default_max_tokens: Optional[int] = None,
        default_top_p: Optional[float] = None,
        message_count: Optional[int] = None,
        last_message_at: Optional[datetime] = None,
        updated_by: Optional[str] = None,
    ) -> Conversation:
        """Update a conversation.

        Args:
            conversation_id: Conversation ID.
            title: Optional new title.
            metadata: Optional new metadata.

        Returns:
            Updated Conversation instance.

        Raises:
            NotFoundError: If conversation not found.
        """
        conversation = self.get_by_id(conversation_id)
        if not conversation:
            raise NotFoundError(f"Conversation not found: {conversation_id}")

        if title is not None:
            conversation.title = title
        if metadata is not None:
            conversation.metadata_json = metadata
        if status is not None:
            conversation.status = status
        if system_prompt is not None:
            conversation.system_prompt = system_prompt
        if default_model_ref is not None:
            conversation.default_model_ref = default_model_ref
        if default_temperature is not None:
            conversation.default_temperature = default_temperature
        if default_max_tokens is not None:
            conversation.default_max_tokens = default_max_tokens
        if default_top_p is not None:
            conversation.default_top_p = default_top_p
        if message_count is not None:
            conversation.message_count = message_count
        if last_message_at is not None:
            conversation.last_message_at = last_message_at
        if updated_by is not None:
            conversation.updated_by = updated_by

        from app.kernel.commons.time import utc_now
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

    def get_latest_by_conversation(self, conversation_id: str) -> Optional[Message]:
        """Get latest message in a conversation ordered by creation time."""
        query = (
            select(Message)
            .where(
                and_(
                    Message.conversation_id == conversation_id,
                    Message.tenant_id == self.ctx.tenant_id,
                    Message.workspace_id == self.ctx.workspace_id,
                )
            )
            .order_by(desc(Message.created_at), desc(Message.id))
            .limit(1)
        )
        result = self.db.exec(query).first()
        return self._unwrap_result(result)

    def list_ancestry(
        self,
        conversation_id: str,
        head_message_id: str,
        limit: int = 100,
    ) -> List[Message]:
        """List ancestor chain from root to the given head message."""
        if not head_message_id or limit <= 0:
            return []

        ancestry: List[Message] = []
        visited: set[str] = set()
        current_id: Optional[str] = head_message_id

        while current_id and len(ancestry) < limit:
            if current_id in visited:
                break
            visited.add(current_id)

            message = self.get_by_id(current_id)
            if not message:
                break
            if message.conversation_id != conversation_id:
                break

            ancestry.append(message)
            current_id = message.parent_id

        ancestry.reverse()
        return ancestry
    
    def list_by_conversation(
        self,
        conversation_id: str,
        limit: int = 100,
        offset: int = 0,
        cursor_at: Optional[datetime] = None,
        cursor_id: Optional[str] = None,
    ) -> List[Message]:
        """List messages in a conversation.
        
        Args:
            conversation_id: Conversation ID.
            limit: Maximum number of messages.
            offset: Offset for pagination.
            cursor_at: Created_at cursor for pagination.
            cursor_id: Message ID cursor for pagination.
            
        Returns:
            List of Message instances.
        """
        query = select(Message).where(
            and_(
                Message.conversation_id == conversation_id,
                Message.tenant_id == self.ctx.tenant_id,
                Message.workspace_id == self.ctx.workspace_id,
            )
        )

        if cursor_at and cursor_id:
            query = query.where(
                or_(
                    Message.created_at > cursor_at,
                    and_(
                        Message.created_at == cursor_at,
                        Message.id > cursor_id,
                    ),
                )
            )
        elif offset:
            query = query.offset(offset)

        query = query.order_by(Message.created_at, Message.id).limit(limit)
        
        results = list(self.db.exec(query).all())
        return self._unwrap_all(results)
    
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
        result = self.db.exec(query).one()
        if result is None:
            return 0
        if isinstance(result, int):
            return result
        return int(result[0])
