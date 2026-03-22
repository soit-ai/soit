"""Lightweight chat input schemas reused by agent-facing APIs."""

from typing import Optional, Dict, Any

from pydantic import BaseModel, Field


class ChatMessageInput(BaseModel):
    """Schema for chat message input."""

    role: str = Field(..., pattern="^(system|user|assistant|tool)$")
    """Message role."""

    content: str = Field(..., min_length=1)
    """Message content."""

    metadata: Optional[Dict[str, Any]] = None
    """Optional message metadata."""
