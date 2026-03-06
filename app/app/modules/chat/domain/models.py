""" models

Chat domain models (Conversation, Message).
"""

from typing import Optional, Dict, Any
from datetime import datetime
from sqlmodel import SQLModel, Field, Column, JSON
from sqlalchemy import Text

from app.kernel.commons.time import utc_now


class Conversation(SQLModel, table=True):
    """Conversation model - represents a chat conversation."""
    
    __tablename__ = "conversations"
    
    id: str = Field(primary_key=True)
    """Conversation ID."""
    
    tenant_id: str = Field(index=True)
    """Tenant ID."""
    
    workspace_id: str = Field(index=True)
    """Workspace ID."""

    app_id: Optional[str] = Field(default=None, index=True)
    """Associated chat app ID."""
    
    title: Optional[str] = Field(default=None, nullable=True, max_length=512)
    """Conversation title."""

    status: str = Field(default="active")
    """Conversation status: active, archived."""

    metadata_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    """Conversation metadata."""

    system_prompt: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    """Default system prompt."""

    default_model_ref: Optional[str] = Field(default=None, nullable=True)
    """Default model reference."""

    default_temperature: Optional[float] = Field(default=None, nullable=True)
    """Default temperature."""

    default_max_tokens: Optional[int] = Field(default=None, nullable=True)
    """Default max tokens."""

    default_top_p: Optional[float] = Field(default=None, nullable=True)
    """Default top-p value."""

    message_count: int = Field(default=0)
    """Message count."""

    last_message_at: Optional[datetime] = Field(default=None, nullable=True)
    """Last message timestamp."""

    created_by: Optional[str] = Field(default=None, nullable=True)
    """User ID who created."""

    updated_by: Optional[str] = Field(default=None, nullable=True)
    """User ID who last updated."""

    deleted_at: Optional[datetime] = Field(default=None, nullable=True)
    """Deletion timestamp (soft delete)."""
    
    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""
    
    updated_at: datetime = Field(default_factory=utc_now)
    """Last update timestamp."""


class Message(SQLModel, table=True):
    """Message model - represents a message in a conversation."""
    
    __tablename__ = "messages"
    
    id: str = Field(primary_key=True)
    """Message ID."""
    
    tenant_id: str = Field(index=True)
    """Tenant ID."""
    
    workspace_id: str = Field(index=True)
    """Workspace ID."""
    
    conversation_id: str = Field(foreign_key="conversations.id", index=True)
    """Conversation ID (foreign key)."""

    parent_id: Optional[str] = Field(default=None, foreign_key="messages.id", index=True, nullable=True)
    """Parent message ID for branch threading."""
    
    role: str = Field()
    """Message role (user, assistant, system)."""

    content: str = Field(sa_column=Column(Text))
    """Message content."""

    model_ref: Optional[str] = Field(default=None, nullable=True)
    """Model reference for assistant responses."""

    tokens_prompt: Optional[int] = Field(default=None, nullable=True)
    """Prompt tokens for the completion."""

    tokens_completion: Optional[int] = Field(default=None, nullable=True)
    """Completion tokens for the response."""

    finish_reason: Optional[str] = Field(default=None, nullable=True)
    """Finish reason (stop, length, etc.)."""

    run_id: Optional[str] = Field(default=None, nullable=True, index=True)
    """Run ID for trace correlation."""

    created_by: Optional[str] = Field(default=None, nullable=True)
    """User ID who created."""

    metadata_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    """Message metadata (model, tokens, etc.)."""
    
    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""
