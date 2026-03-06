""" schemas

Agent domain schemas.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

from app.modules.chat.application.schemas import ChatMessageInput


class AgentCreate(BaseModel):
    """Schema for creating an agent."""

    name: str = Field(..., min_length=1, max_length=256)
    """Agent name."""

    description: Optional[str] = Field(default=None, max_length=2000)
    """Agent description."""

    visibility: str = Field(default="private", pattern="^(private|workspace|tenant|public)$")
    """Agent visibility."""

    tags: Optional[List[str]] = None
    """Agent tags."""


class AgentUpdate(BaseModel):
    """Schema for updating an agent."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=256)
    """Agent name."""

    description: Optional[str] = Field(default=None, max_length=2000)
    """Agent description."""

    status: Optional[str] = Field(default=None, pattern="^(active|archived|disabled)$")
    """Agent status."""

    visibility: Optional[str] = Field(default=None, pattern="^(private|workspace|tenant|public)$")
    """Agent visibility."""

    tags: Optional[List[str]] = None
    """Agent tags."""


class AgentResponse(BaseModel):
    """Agent response schema."""

    id: str
    tenant_id: str
    workspace_id: str
    name: str
    description: Optional[str]
    status: str
    visibility: str
    tags: Optional[List[str]]
    current_version_id: Optional[str]
    published_version_id: Optional[str]
    created_by: Optional[str]
    updated_by: Optional[str]
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class AgentVersionCreate(BaseModel):
    """Schema for creating an agent version."""

    system_prompt: Optional[str] = Field(default=None, max_length=8000)
    """System prompt."""

    model_ref: str
    """Model reference."""

    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    """Temperature."""

    max_iterations: Optional[int] = Field(default=None, ge=1, le=50)
    """Max planning iterations."""

    max_tool_calls: Optional[int] = Field(default=None, ge=0, le=100)
    """Max tool calls allowed."""

    max_llm_calls: Optional[int] = Field(default=None, ge=1, le=200)
    """Max LLM calls allowed."""

    max_failures: Optional[int] = Field(default=None, ge=0, le=10)
    """Max failures before stopping."""

    max_runtime_seconds: Optional[int] = Field(default=None, ge=1, le=3600)
    """Max runtime budget in seconds."""

    max_tokens_total: Optional[int] = Field(default=None, ge=1)
    """Max total tokens across LLM calls."""

    max_cost: Optional[float] = Field(default=None, ge=0.0)
    """Max total cost across tool/LLM calls."""

    cost_currency: Optional[str] = None
    """Currency for max cost budget."""

    tool_refs: Optional[List[str]] = None
    """Optional allowed tool refs."""

    memory_strategy: Optional[str] = Field(
        default=None,
        pattern="^(planner_only|system_message|user_message)$",
    )
    """Memory injection strategy."""

    memory_top_k: Optional[int] = Field(default=None, ge=1, le=50)
    """Number of memory items to fetch."""

    verify: Optional[bool] = None
    """Enable response verification."""

    failure_strategy: Optional[str] = Field(
        default=None,
        pattern="^(respond|abort|continue)$",
    )
    """Failure handling strategy when max_failures is exceeded."""


class AgentVersionResponse(BaseModel):
    """Agent version response schema."""

    id: str
    agent_id: str
    version: int
    status: str
    spec_schema: str
    spec_json: Dict[str, Any]
    checksum: Optional[str]
    created_by: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentPublishRequest(BaseModel):
    """Publish agent version request."""

    version_id: str
    """Version ID to publish."""


class AgentRunRequest(BaseModel):
    """Run agent request."""

    messages: List[ChatMessageInput] = Field(..., min_length=1)
    """Conversation messages."""

    model: Optional[str] = None
    """Model reference."""

    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    """Sampling temperature."""

    max_iterations: int = Field(default=8, ge=1, le=50)
    """Max planning iterations."""

    max_tool_calls: int = Field(default=8, ge=0, le=100)
    """Max tool calls allowed."""

    max_llm_calls: int = Field(default=16, ge=1, le=200)
    """Max LLM calls allowed."""

    max_failures: int = Field(default=2, ge=0, le=10)
    """Max failures before stopping."""

    max_runtime_seconds: Optional[int] = Field(default=None, ge=1, le=3600)
    """Max runtime budget in seconds."""

    max_tokens_total: Optional[int] = Field(default=None, ge=1)
    """Max total tokens across LLM calls."""

    max_cost: Optional[float] = Field(default=None, ge=0.0)
    """Max total cost across tool/LLM calls."""

    cost_currency: str = Field(default="USD")
    """Currency for max cost budget."""

    tool_refs: Optional[List[str]] = None
    """Optional allowed tool refs."""

    memory_query: Optional[str] = None
    """Override memory query."""

    memory_strategy: str = Field(
        default="planner_only",
        pattern="^(planner_only|system_message|user_message)$",
    )
    """Memory injection strategy."""

    memory_top_k: int = Field(default=5, ge=1, le=50)
    """Number of memory items to fetch."""

    context_window_messages: Optional[int] = Field(default=None, ge=1, le=200)
    """Max number of recent messages to keep in context."""

    context_window_chars: Optional[int] = Field(default=None, ge=1, le=200000)
    """Max total characters kept across messages."""

    verify: bool = True
    """Enable response verification."""

    failure_strategy: str = Field(
        default="respond",
        pattern="^(respond|abort|continue)$",
    )
    """Failure handling strategy when max_failures is exceeded."""


class AgentRunResponse(BaseModel):
    """Run agent response."""

    run_id: str
    output: str
    model: str
    iterations: int
    tokens_prompt: int = 0
    tokens_completion: int = 0
    finish_reason: Optional[str] = None
    tool_calls: int = 0
    llm_calls: int = 0
    failures: int = 0
    budget_exceeded: bool = False
    budget_reason: Optional[str] = None
    cost_total: float = 0.0
