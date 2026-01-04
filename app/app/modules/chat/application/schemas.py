"""schemas

Chat domain schemas.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field


class ChatMessageInput(BaseModel):
    """Schema for chat message input."""

    role: str = Field(..., pattern="^(system|user|assistant|tool)$")
    """Message role."""

    content: str = Field(..., min_length=1)
    """Message content."""

    metadata: Optional[Dict[str, Any]] = None
    """Optional message metadata."""


class ConversationCreate(BaseModel):
    """Schema for creating a conversation."""

    title: Optional[str] = Field(default=None, max_length=512)
    """Conversation title."""

    metadata: Optional[Dict[str, Any]] = None
    """Conversation metadata."""


class ConversationUpdate(BaseModel):
    """Schema for updating a conversation."""

    title: Optional[str] = Field(default=None, max_length=512)
    """Conversation title."""

    metadata: Optional[Dict[str, Any]] = None
    """Conversation metadata."""


class ConversationResponse(BaseModel):
    """Schema for conversation response."""

    id: str
    tenant_id: str
    workspace_id: str
    title: Optional[str]
    metadata_json: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    """Schema for message response."""

    id: str
    conversation_id: str
    role: str
    content: str
    metadata_json: Optional[Dict[str, Any]]
    created_at: datetime

    class Config:
        from_attributes = True


class ChatCompletionRequest(BaseModel):
    """Schema for chat completion request."""

    conversation_id: Optional[str] = None
    """Conversation ID (optional)."""

    messages: List[ChatMessageInput] = Field(..., min_length=1)
    """Chat messages."""

    model: str = Field(default="model:openai:gpt-3.5-turbo", min_length=1)
    """Model reference (provider:model)."""

    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    """Sampling temperature."""

    max_tokens: Optional[int] = Field(default=None, ge=1)
    """Maximum tokens to generate."""

    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    """Top-p sampling value."""

    stream: bool = False
    """Whether to stream the response."""

    history_limit: int = Field(default=50, ge=0, le=200)
    """Max historical messages to include."""

    title: Optional[str] = Field(default=None, max_length=512)
    """Conversation title (used when creating new conversation)."""

    metadata: Optional[Dict[str, Any]] = None
    """Conversation metadata (used when creating new conversation)."""


class ChatCompletionResponse(BaseModel):
    """Schema for chat completion response."""

    run_id: str
    conversation_id: str
    message: MessageResponse
    model: str
    tokens_prompt: int = 0
    tokens_completion: int = 0
    finish_reason: Optional[str] = None
