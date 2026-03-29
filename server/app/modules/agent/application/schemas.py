""" schemas

Agent domain schemas.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, model_validator



class AgentCreate(BaseModel):
    """Schema for creating an agent."""

    name: str = Field(..., min_length=1, max_length=256)
    """Agent name."""

    description: Optional[str] = Field(default=None, max_length=2000)
    """Agent description."""

    visibility: str = Field(default="private", pattern="^(private|workspace|tenant|public)$")
    """Agent visibility."""

    icon_url: Optional[str] = Field(default=None, max_length=2000)
    """Agent icon URL."""

    category: Optional[str] = Field(default=None, max_length=128)
    """Agent category."""

    is_public: bool = False
    """Whether the agent is publicly discoverable."""

    featured: bool = False
    """Whether the agent is featured in listings."""

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

    icon_url: Optional[str] = Field(default=None, max_length=2000)
    """Agent icon URL."""

    category: Optional[str] = Field(default=None, max_length=128)
    """Agent category."""

    is_public: Optional[bool] = None
    """Whether the agent is publicly discoverable."""

    featured: Optional[bool] = None
    """Whether the agent is featured in listings."""

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
    icon_url: Optional[str]
    category: Optional[str]
    is_public: bool
    featured: bool
    downloads_count: int
    rating: Optional[float]
    reviews_count: int
    published_at: Optional[datetime]
    tags: Optional[List[str]]
    current_version_id: Optional[str]
    published_version_id: Optional[str]
    created_by: Optional[str]
    updated_by: Optional[str]
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class AgentCapabilityBindings(BaseModel):
    """Unified capability bindings attached to an agent version."""

    model_config = ConfigDict(extra="forbid")

    model_ref: Optional[str] = None
    knowledge_refs: Optional[List[str]] = None
    tool_refs: Optional[List[str]] = None
    workflow_refs: Optional[List[str]] = None
    skill_refs: Optional[List[str]] = None
    plugin_refs: Optional[List[str]] = None


class AgentVersionCreate(BaseModel):
    """Schema for creating an agent version."""

    model_config = ConfigDict(extra="forbid")

    system_prompt: Optional[str] = Field(default=None, max_length=8000)
    """System prompt."""

    model_ref: Optional[str] = None
    """Model reference."""

    knowledge_refs: Optional[List[str]] = None
    """Optional knowledge base refs bound into agent RAG config."""

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

    workflow_refs: Optional[List[str]] = None
    """Optional workflow refs bound into the agent capability set."""

    skill_refs: Optional[List[str]] = None
    """Optional skill refs bound into the agent capability set."""

    plugin_refs: Optional[List[str]] = None
    """Optional plugin refs bound into the agent capability set."""

    bindings: Optional[AgentCapabilityBindings] = None
    """Unified capability binding input. Legacy top-level refs remain supported."""

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

    @model_validator(mode="after")
    def validate_model_ref(self) -> "AgentVersionCreate":
        nested_model_ref = self.bindings.model_ref if self.bindings else None
        if self.model_ref and nested_model_ref and self.model_ref != nested_model_ref:
            raise ValueError("model_ref conflicts with bindings.model_ref")
        if not (self.model_ref or nested_model_ref):
            raise ValueError("model_ref or bindings.model_ref is required")
        return self


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


class AgentBindingResponse(BaseModel):
    """Agent binding response schema."""

    id: str
    agent_id: str
    agent_version_id: Optional[str]
    binding_type: str
    target_id: Optional[str]
    target_key: Optional[str]
    config_json: Dict[str, Any]
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentPublishRequest(BaseModel):
    """Publish agent version request."""

    version_id: str
    """Version ID to publish."""


class ChatMessageInput(BaseModel):
    """Schema for chat message input."""

    role: str = Field(..., pattern="^(system|user|assistant|tool)$")
    """Message role."""

    content: str = Field(..., min_length=1)
    """Message content."""

    metadata: Optional[Dict[str, Any]] = None
    """Optional message metadata."""


class AgentRunRequest(BaseModel):
    """Run agent request."""

    messages: List[ChatMessageInput] = Field(..., min_length=1)
    """Conversation messages."""

    thread_id: Optional[str] = None
    """Existing thread ID to append messages into."""

    thread_title: Optional[str] = Field(default=None, max_length=512)
    """Optional title used when a new thread is created."""

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
    response_id: Optional[str] = None
    thread_id: Optional[str] = None
    task_id: Optional[str] = None
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
