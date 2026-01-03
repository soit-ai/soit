""" service

Chat domain service.
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.kernel.commons.errors import NotFoundError
from app.kernel.commons.ids import generate_ulid
from app.kernel.commons.time import utc_now
from app.modules.chat.domain.models import Conversation, Message
from app.modules.chat.application.ports import ConversationRepositoryPort, MessageRepositoryPort


class ChatService:
    """Chat domain service."""
    
    def __init__(
        self,
        db: Session,
        ctx: RequestContext,
        conversation_repo: ConversationRepositoryPort,
        message_repo: MessageRepositoryPort,
    ):
        """Initialize chat service.
        
        Args:
            db: Database session.
            ctx: Request context.
            conversation_repo: Conversation repository.
            message_repo: Message repository.
        """
        self.db = db
        self.ctx = ctx
        self.conversation_repo = conversation_repo
        self.message_repo = message_repo
    
    def create_conversation(
        self,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Conversation:
        """Create a new conversation.
        
        Args:
            title: Optional conversation title.
            metadata: Optional conversation metadata.
            
        Returns:
            Created Conversation instance.
        """
        conversation = Conversation(
            id=generate_ulid(),
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            title=title,
            metadata_json=metadata,
        )
        
        return self.conversation_repo.create(conversation)
    
    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Message:
        """Add a message to a conversation.
        
        Args:
            conversation_id: Conversation ID.
            role: Message role (user, assistant, system).
            content: Message content.
            metadata: Optional message metadata.
            
        Returns:
            Created Message instance.
            
        Raises:
            NotFoundError: If conversation not found.
        """
        # Verify conversation exists
        conversation = self.conversation_repo.get_by_id(conversation_id)
        if not conversation:
            raise NotFoundError(f"Conversation not found: {conversation_id}")
        
        # Create message
        message = Message(
            id=generate_ulid(),
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            conversation_id=conversation_id,
            role=role,
            content=content,
            metadata_json=metadata,
        )
        
        message = self.message_repo.create(message)
        
        # Update conversation updated_at
        conversation.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(conversation)
        
        return message
    
    def get_conversation(self, conversation_id: str) -> Conversation:
        """Get conversation by ID.
        
        Args:
            conversation_id: Conversation ID.
            
        Returns:
            Conversation instance.
            
        Raises:
            NotFoundError: If conversation not found.
        """
        conversation = self.conversation_repo.get_by_id(conversation_id)
        if not conversation:
            raise NotFoundError(f"Conversation not found: {conversation_id}")
        return conversation
    
    def list_conversations(
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
        return self.conversation_repo.list(limit=limit, offset=offset)
    
    def get_messages(
        self,
        conversation_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Message]:
        """Get messages in a conversation.
        
        Args:
            conversation_id: Conversation ID.
            limit: Maximum number of messages.
            offset: Offset for pagination.
            
        Returns:
            List of Message instances.
            
        Raises:
            NotFoundError: If conversation not found.
        """
        # Verify conversation exists
        conversation = self.conversation_repo.get_by_id(conversation_id)
        if not conversation:
            raise NotFoundError(f"Conversation not found: {conversation_id}")
        
        return self.message_repo.list_by_conversation(
            conversation_id=conversation_id,
            limit=limit,
            offset=offset,
        )
    
    def delete_conversation(self, conversation_id: str) -> None:
        """Delete a conversation (soft delete).
        
        Args:
            conversation_id: Conversation ID.
            
        Raises:
            NotFoundError: If conversation not found.
        """
        self.conversation_repo.soft_delete(conversation_id)

