""" schemas

Agent domain schemas.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class AgentCreate(BaseModel):
    """Schema for creating an agent."""

    name: str = Field(..., min_length=1, max_length=256)
    """Agent name."""

    description: str | None = Field(default=None, max_length=2000)
    """Agent description."""

    visibility: str = Field(default="private", pattern="^(private|workspace|tenant|public)$")
    """Agent visibility."""

    icon_url: str | None = Field(default=None, max_length=2000)
    """Agent icon URL."""

    category: str | None = Field(default=None, max_length=128)
    """Agent category."""

    is_public: bool = False
    """Whether the agent is publicly discoverable."""

    featured: bool = False
    """Whether the agent is featured in listings."""

    tags: list[str] | None = None
    """Agent tags."""


class AgentUpdate(BaseModel):
    """Schema for updating an agent."""

    name: str | None = Field(default=None, min_length=1, max_length=256)
    """Agent name."""

    description: str | None = Field(default=None, max_length=2000)
    """Agent description."""

    status: str | None = Field(default=None, pattern="^(active|archived|disabled)$")
    """Agent status."""

    visibility: str | None = Field(default=None, pattern="^(private|workspace|tenant|public)$")
    """Agent visibility."""

    icon_url: str | None = Field(default=None, max_length=2000)
    """Agent icon URL."""

    category: str | None = Field(default=None, max_length=128)
    """Agent category."""

    is_public: bool | None = None
    """Whether the agent is publicly discoverable."""

    featured: bool | None = None
    """Whether the agent is featured in listings."""

    tags: list[str] | None = None
    """Agent tags."""


class AgentResponse(BaseModel):
    """Agent response schema."""

    id: str
    tenant_id: str
    workspace_id: str
    name: str
    description: str | None
    status: str
    visibility: str
    icon_url: str | None
    category: str | None
    is_public: bool
    featured: bool
    downloads_count: int
    rating: float | None
    reviews_count: int
    published_at: datetime | None
    tags: list[str] | None
    current_version_id: str | None
    published_version_id: str | None
    created_by: str | None
    updated_by: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class AgentCapabilityBindings(BaseModel):
    """Unified capability bindings attached to an agent version."""

    model_config = ConfigDict(extra="forbid")

    model_ref: str
    knowledge_refs: list[str] = Field(default_factory=list)
    tool_refs: list[str] = Field(default_factory=list)
    workflow_refs: list[str] = Field(default_factory=list)
    skill_refs: list[str] = Field(default_factory=list)


class AgentVersionCreate(BaseModel):
    """Schema for creating an agent version."""

    model_config = ConfigDict(extra="forbid")

    system_prompt: str | None = Field(default=None, max_length=8000)
    """System prompt."""

    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    """Temperature."""

    max_iterations: int | None = Field(default=None, ge=1, le=50)
    """Max planning iterations."""

    max_tool_calls: int | None = Field(default=None, ge=0, le=100)
    """Max tool calls allowed."""

    max_llm_calls: int | None = Field(default=None, ge=1, le=200)
    """Max LLM calls allowed."""

    max_failures: int | None = Field(default=None, ge=0, le=10)
    """Max failures before stopping."""

    max_runtime_seconds: int | None = Field(default=None, ge=1, le=3600)
    """Max runtime budget in seconds."""

    max_tokens_total: int | None = Field(default=None, ge=1)
    """Max total tokens across LLM calls."""

    max_cost: float | None = Field(default=None, ge=0.0)
    """Max total cost across tool/LLM calls."""

    cost_currency: str | None = None
    """Currency for max cost budget."""

    rag_top_k: int | None = Field(default=None, ge=1, le=50)
    """Number of knowledge chunks retrieved for each turn."""

    rag_strategy: str | None = Field(
        default=None,
        pattern="^(system_message|planner_context)$",
    )
    """How published knowledge context is injected into the runtime."""

    context_window_messages: int | None = Field(default=None, ge=1, le=200)
    """Maximum trusted conversation messages rebuilt from the thread ledger."""

    context_window_chars: int | None = Field(default=None, ge=1, le=200000)
    """Maximum trusted conversation characters rebuilt from the thread ledger."""

    bindings: AgentCapabilityBindings
    """Unified capability binding input."""

    memory_strategy: str | None = Field(
        default=None,
        pattern="^(planner_only|system_message|user_message)$",
    )
    """Memory injection strategy."""

    memory_top_k: int | None = Field(default=None, ge=1, le=50)
    """Number of memory items to fetch."""

    verify: bool | None = None
    """Enable response verification."""

    failure_strategy: str | None = Field(
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
    spec_json: dict[str, Any]
    checksum: str | None
    created_by: str | None
    created_at: datetime
    review_status: str = "none"
    review_requested_at: datetime | None = None
    review_requested_by: str | None = None
    review_note: str | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class AgentVersionReviewRequest(BaseModel):
    """Move a draft between review states.

    `request` puts it in front of a reviewer, `approve` and `request_changes`
    are the two answers, and `withdraw` takes it back off the queue.
    """

    action: Literal["request", "approve", "request_changes", "withdraw"]
    note: str | None = Field(default=None, max_length=512)


class DraftAwaitingReviewResponse(BaseModel):
    """One draft somebody is waiting on, across the workspace."""

    version_id: str
    agent_id: str
    agent_name: str | None = None
    version: int
    review_status: str
    review_note: str | None = None
    review_requested_at: datetime | None = None
    review_requested_by: str | None = None


class AgentReleaseResponse(BaseModel):
    """Agent release ledger response schema."""

    id: str
    agent_id: str
    version_id: str
    action: str
    scope: str
    status: str
    from_version_id: str | None
    to_version_id: str
    notes: str | None
    rollback_of_publish_id: str | None
    created_by: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentBindingResponse(BaseModel):
    """Agent binding response schema."""

    id: str
    agent_id: str
    agent_version_id: str | None
    binding_type: str
    target_id: str | None
    target_key: str | None
    target_label: str | None = None
    """Display name of the bound capability, resolved from the catalog."""
    config_json: dict[str, Any]
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentWorkbenchSummary(BaseModel):
    """Agent workbench aggregate metrics."""

    total_agents: int
    configured_agents: int
    running_agents: int
    today_calls: int
    avg_latency_ms: int | None
    success_rate: float | None
    pending_exceptions: int
    updated_at: datetime


class AgentWorkbenchTabs(BaseModel):
    """Counts for Agent workbench filter tabs."""

    all: int
    high_calls: int
    low_success: int
    long_latency: int
    unconfigured: int


class AgentWorkbenchCapability(BaseModel):
    """Capability binding displayed in the Agent workbench table."""

    type: str
    target_id: str | None = None
    target_key: str | None = None
    label: str


class AgentWorkbenchRow(BaseModel):
    """Agent row with runtime health for the workbench."""

    id: str
    name: str
    description: str | None
    status: str
    capabilities: list[AgentWorkbenchCapability] = Field(default_factory=list)
    today_calls: int
    avg_latency_ms: int | None
    success_rate: float | None
    recent_exception_count: int
    owner: str | None
    last_run_at: datetime | None
    action_enabled: bool
    updated_at: datetime


class AgentWorkbenchResponse(BaseModel):
    """Full Agent workbench response."""

    summary: AgentWorkbenchSummary
    tabs: AgentWorkbenchTabs
    items: list[AgentWorkbenchRow]
    next_page_token: str | None = None
    page_size: int


class AgentWorkbenchItemsResponse(BaseModel):
    """Paginated Agent workbench table rows."""

    items: list[AgentWorkbenchRow]
    next_page_token: str | None = None
    page_size: int


class AgentCapabilityResponse(BaseModel):
    """Runtime capability item available for Agent assembly."""

    ref: str
    kind: str
    name: str
    source_kind: str
    source_id: str | None = None
    source_version: str | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class AgentPublishRequest(BaseModel):
    """Publish agent version request."""

    version_id: str
    """Version ID to publish."""

    notes: str | None = Field(default=None, max_length=2000)
    """Optional publish notes."""


class AgentRollbackRequest(BaseModel):
    """Rollback agent version request."""

    version_id: str
    """Version ID to roll back to."""

    notes: str | None = Field(default=None, max_length=2000)
    """Optional rollback notes."""


class ChatMessageInput(BaseModel):
    """Schema for chat message input."""

    role: str = Field(..., pattern="^(system|user|assistant|tool)$")
    """Message role."""

    content: str = Field(..., min_length=1)
    """Message content."""

    metadata: dict[str, Any] | None = None
    """Optional message metadata."""


class AgentRunRequest(BaseModel):
    """Public request for one stateful Agent turn."""

    model_config = ConfigDict(extra="forbid")

    input: str = Field(..., min_length=1, max_length=200000)
    """Current user input only; conversation history is rebuilt by SOIT."""

    thread_id: str | None = None
    """Existing thread to continue, or omitted to create one."""

    request_id: str | None = Field(default=None, max_length=256)
    """Caller-provided correlation identifier."""


class _AgentRuntimeOptions(BaseModel):
    """Internal execution options resolved from an immutable Agent version."""

    model_config = ConfigDict(extra="forbid")

    messages: list[ChatMessageInput] = Field(..., min_length=1)
    """Conversation messages."""

    thread_id: str | None = None
    """Existing thread ID to append messages into."""

    request_id: str | None = Field(default=None, max_length=256)
    """Correlation identifier propagated to Run and Response."""

    thread_title: str | None = Field(default=None, max_length=512)
    """Optional title used when a new thread is created."""

    max_iterations: int = Field(default=8, ge=1, le=50)
    """Max planning iterations."""

    max_tool_calls: int = Field(default=8, ge=0, le=100)
    """Max tool calls allowed."""

    max_llm_calls: int = Field(default=16, ge=1, le=200)
    """Max LLM calls allowed."""

    max_failures: int = Field(default=2, ge=0, le=10)
    """Max failures before stopping."""

    max_runtime_seconds: int | None = Field(default=None, ge=1, le=3600)
    """Max runtime budget in seconds."""

    max_tokens_total: int | None = Field(default=None, ge=1)
    """Max total tokens across LLM calls."""

    max_cost: float | None = Field(default=None, ge=0.0)
    """Max total cost across tool/LLM calls."""

    cost_currency: str = Field(default="USD")
    """Currency for max cost budget."""

    rag_top_k: int = Field(default=5, ge=1, le=50)
    """Number of chunks to retrieve per knowledge base."""

    rag_strategy: str = Field(
        default="system_message",
        pattern="^(system_message|planner_context)$",
    )
    """How to inject RAG context: system_message prepends, planner_context passes to planner."""

    memory_query: str | None = None
    """Override memory query."""

    memory_strategy: str | None = Field(
        default=None,
        pattern="^(planner_only|system_message|user_message)$",
    )
    """Memory injection strategy."""

    memory_top_k: int | None = Field(default=None, ge=1, le=50)
    """Number of memory items to fetch."""

    context_window_messages: int | None = Field(default=None, ge=1, le=200)
    """Max number of recent messages to keep in context."""

    context_window_chars: int | None = Field(default=None, ge=1, le=200000)
    """Max total characters kept across messages."""

    verify: bool = True
    """Enable response verification."""

    failure_strategy: str = Field(
        default="respond",
        pattern="^(respond|abort|continue)$",
    )
    """Failure handling strategy when max_failures is exceeded."""

    show_reasoning: bool = False
    """Expose provider-visible reasoning through the interaction protocol."""

    reasoning_effort: str | None = Field(default=None, max_length=32)
    """Optional provider reasoning effort hint."""


class AgentRuntimeRequest(_AgentRuntimeOptions):
    """Internal runtime request resolved from a published agent version."""

    model_ref: str
    """Resolved model reference from the published agent version."""

    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    """Resolved model temperature from the published agent version."""

    knowledge_refs: list[str] = Field(default_factory=list)
    """Resolved knowledge bindings from the published agent version."""

    tool_refs: list[str] = Field(default_factory=list)
    """Resolved tool bindings from the published agent version."""

    workflow_refs: list[str] = Field(default_factory=list)
    """Resolved workflow bindings from the published agent version."""

    skill_refs: list[str] = Field(default_factory=list)
    """Resolved skill bindings from the published agent version."""

    system_prompt: str | None = Field(default=None, max_length=8000)
    """Resolved system prompt from the published agent version."""

    task_id: str | None = None
    """Authoritative Task used by runtime governance checkpoints."""

    agent_id: str | None = None
    """Authoritative Agent identity used by runtime governance checkpoints."""

    approval_responses: list[dict[str, Any]] = Field(default_factory=list)
    """Resolved AG-UI interrupt responses for a resumed execution segment."""

    approval_checkpoint: dict[str, Any] | None = None
    """Durable runtime state captured immediately before an approved side effect."""


class AgentRunResponse(BaseModel):
    """Run agent response."""

    run_id: str
    response_id: str | None = None
    thread_id: str | None = None
    task_id: str | None = None
    request_id: str | None = None
    output: str
    model: str
    iterations: int
    tokens_prompt: int = 0
    tokens_completion: int = 0
    finish_reason: str | None = None
    tool_calls: int = 0
    llm_calls: int = 0
    failures: int = 0
    budget_exceeded: bool = False
    budget_reason: str | None = None
    cost_total: float = 0.0
    citations: list[dict[str, Any]] = Field(default_factory=list)


class AgentCancelResponse(BaseModel):
    """Result of explicitly canceling one Agent execution."""

    run_id: str
    status: str
    task_ids: list[str] = Field(default_factory=list)
    response_ids: list[str] = Field(default_factory=list)
