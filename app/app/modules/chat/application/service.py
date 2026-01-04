""" service

Chat domain service.
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.kernel.commons.errors import NotFoundError, ValidationError
from app.kernel.commons.ids import generate_ulid, generate_run_id
from app.kernel.commons.time import utc_now
from app.kernel.trace.writer import TraceWriter
from app.kernel.ports.llm.interface import LLMPort, ChatMessage
from app.modules.chat.domain.models import Conversation, Message
from app.modules.chat.application.ports import ConversationRepositoryPort, MessageRepositoryPort
from app.modules.chat.application.schemas import (
    ConversationCreate,
    ConversationUpdate,
    ChatCompletionRequest,
)


class ChatService:
    """Chat domain service."""
    
    def __init__(
        self,
        db: Session,
        ctx: RequestContext,
        conversation_repo: ConversationRepositoryPort,
        message_repo: MessageRepositoryPort,
        llm_port: Optional[LLMPort] = None,
        trace_writer: Optional[TraceWriter] = None,
    ):
        """Initialize chat service.
        
        Args:
            db: Database session.
            ctx: Request context.
            conversation_repo: Conversation repository.
            message_repo: Message repository.
            llm_port: Optional LLM port.
            trace_writer: Optional trace writer.
        """
        self.db = db
        self.ctx = ctx
        self.conversation_repo = conversation_repo
        self.message_repo = message_repo
        self.llm_port = llm_port
        self.trace_writer = trace_writer
    
    def create_conversation(
        self,
        data: ConversationCreate,
    ) -> Conversation:
        """Create a new conversation.
        
        Args:
            data: Conversation creation data.
            
        Returns:
            Created Conversation instance.
        """
        conversation = Conversation(
            id=generate_ulid(),
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            title=data.title,
            status=data.status,
            metadata_json=data.metadata,
            system_prompt=data.system_prompt,
            default_model_ref=data.default_model_ref,
            default_temperature=data.default_temperature,
            default_max_tokens=data.default_max_tokens,
            default_top_p=data.default_top_p,
            created_by=self.ctx.user_id,
            updated_by=self.ctx.user_id,
        )
        
        return self.conversation_repo.create(conversation)

    def update_conversation(
        self,
        conversation_id: str,
        data: ConversationUpdate,
    ) -> Conversation:
        """Update a conversation.

        Args:
            conversation_id: Conversation ID.
            data: Conversation update data.

        Returns:
            Updated Conversation instance.
        """
        return self.conversation_repo.update(
            conversation_id=conversation_id,
            title=data.title,
            metadata=data.metadata,
            status=data.status,
            system_prompt=data.system_prompt,
            default_model_ref=data.default_model_ref,
            default_temperature=data.default_temperature,
            default_max_tokens=data.default_max_tokens,
            default_top_p=data.default_top_p,
            updated_by=self.ctx.user_id,
        )
    
    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        model_ref: Optional[str] = None,
        tokens_prompt: Optional[int] = None,
        tokens_completion: Optional[int] = None,
        finish_reason: Optional[str] = None,
        run_id: Optional[str] = None,
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
            model_ref=model_ref,
            tokens_prompt=tokens_prompt,
            tokens_completion=tokens_completion,
            finish_reason=finish_reason,
            run_id=run_id,
            created_by=self.ctx.user_id,
            metadata_json=metadata,
        )
        
        message = self.message_repo.create(message)
        
        # Update conversation stats
        conversation.updated_at = utc_now()
        conversation.updated_by = self.ctx.user_id
        conversation.last_message_at = utc_now()
        if conversation.message_count is None:
            conversation.message_count = 0
        conversation.message_count += 1
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

    def _resolve_history_messages(
        self,
        conversation_id: str,
        history_limit: int,
    ) -> List[Message]:
        """Load recent messages for a conversation.

        Args:
            conversation_id: Conversation ID.
            history_limit: Max messages to include.

        Returns:
            List of recent Message instances (oldest to newest).
        """
        if history_limit <= 0:
            return []

        total = self.message_repo.count_by_conversation(conversation_id)
        offset = max(total - history_limit, 0)
        return self.message_repo.list_by_conversation(
            conversation_id=conversation_id,
            limit=history_limit,
            offset=offset,
        )

    def _infer_title(self, messages: List[ChatMessage]) -> Optional[str]:
        """Infer a short title from messages.

        Args:
            messages: Chat messages.

        Returns:
            Short title or None.
        """
        for msg in messages:
            if msg.role == "user" and msg.content:
                return msg.content.strip()[:80]
        return None

    async def create_completion(
        self,
        data: ChatCompletionRequest,
    ) -> Dict[str, Any]:
        """Create a chat completion and persist messages.

        Args:
            data: Chat completion request data.

        Returns:
            Completion result dictionary.
        """
        if not self.llm_port:
            raise ValidationError("LLM gateway not available")

        conversation: Optional[Conversation] = None
        if data.conversation_id:
            conversation = self.conversation_repo.get_by_id(data.conversation_id)
            if not conversation:
                raise NotFoundError(f"Conversation not found: {data.conversation_id}")
        else:
            conversation = self.create_conversation(
                ConversationCreate(title=data.title, metadata=data.metadata)
            )

        history_messages = self._resolve_history_messages(
            conversation_id=conversation.id,
            history_limit=data.history_limit,
        )

        llm_messages = [
            ChatMessage(role=msg.role, content=msg.content)
            for msg in history_messages
        ]
        llm_messages.extend(
            ChatMessage(role=msg.role, content=msg.content)
            for msg in data.messages
        )

        if conversation.system_prompt and not any(msg.role == "system" for msg in llm_messages):
            llm_messages = [ChatMessage(role="system", content=conversation.system_prompt)] + llm_messages

        if not llm_messages:
            raise ValidationError("No messages provided for completion")

        run_id = generate_run_id()
        if self.trace_writer:
            run = self.trace_writer.create_run(
                mode="chat",
                app_version_id=conversation.id,
                input_summary=llm_messages[-1].content[:8192],
            )
            run_id = run.id
            self.trace_writer.update_run_status(run_id, "running")

        try:
            for msg in data.messages:
                self.add_message(
                    conversation_id=conversation.id,
                    role=msg.role,
                    content=msg.content,
                    metadata=msg.metadata,
                    run_id=run_id,
                )

            if not conversation.title:
                inferred_title = self._infer_title(llm_messages)
                if inferred_title:
                    self.conversation_repo.update(
                        conversation_id=conversation.id,
                        title=inferred_title,
                        metadata=conversation.metadata_json,
                    )

            model_ref = data.model or conversation.default_model_ref or "model:openai:gpt-3.5-turbo"
            temperature = data.temperature if data.temperature is not None else conversation.default_temperature
            max_tokens = data.max_tokens if data.max_tokens is not None else conversation.default_max_tokens
            top_p = data.top_p if data.top_p is not None else conversation.default_top_p

            response = await self.llm_port.chat(
                messages=llm_messages,
                model=model_ref,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                run_id=run_id,
            )

            assistant_message = self.add_message(
                conversation_id=conversation.id,
                role="assistant",
                content=response.text,
                model_ref=response.model or model_ref,
                tokens_prompt=response.tokens_prompt,
                tokens_completion=response.tokens_completion,
                finish_reason=response.finish_reason,
                run_id=run_id,
                metadata={
                    "model": response.model or model_ref,
                    "tokens_prompt": response.tokens_prompt,
                    "tokens_completion": response.tokens_completion,
                    "finish_reason": response.finish_reason,
                    "run_id": run_id,
                },
            )

            if self.trace_writer:
                self.trace_writer.update_run_status(
                    run_id,
                    "succeeded",
                    output_summary=response.text[:8192] if response.text else None,
                )

            return {
                "run_id": run_id,
                "conversation": conversation,
                "message": assistant_message,
                "model": response.model or model_ref,
                "tokens_prompt": response.tokens_prompt,
                "tokens_completion": response.tokens_completion,
                "finish_reason": response.finish_reason,
            }
        except Exception as exc:
            if self.trace_writer:
                self.trace_writer.update_run_status(
                    run_id,
                    "failed",
                    output_summary=str(exc)[:8192],
                )
            raise
    
    def delete_conversation(self, conversation_id: str) -> None:
        """Delete a conversation (soft delete).
        
        Args:
            conversation_id: Conversation ID.
            
        Raises:
            NotFoundError: If conversation not found.
        """
        self.conversation_repo.soft_delete(conversation_id)
