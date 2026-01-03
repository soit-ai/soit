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
    
    title: Optional[str] = Field(default=None, nullable=True, max_length=512)
    """Conversation title."""
    
    metadata_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    """Conversation metadata."""
    
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
    
    role: str = Field()
    """Message role (user, assistant, system)."""
    
    content: str = Field(sa_column=Column(Text))
    """Message content."""
    
    metadata_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    """Message metadata (model, tokens, etc.)."""
    
    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""

