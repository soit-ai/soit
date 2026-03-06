""" schemas

Bot domain schemas.
"""

from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, model_validator

from app.modules.chat.application.schemas import ChatMessageInput


class BotCreate(BaseModel):
    """Schema for creating a bot."""

    name: str = Field(..., min_length=1, max_length=256)
    """Bot name."""

    description: Optional[str] = Field(default=None, max_length=2000)
    """Bot description."""

    visibility: str = Field(default="private", pattern="^(private|workspace|tenant|public)$")
    """Bot visibility."""

    tags: Optional[List[str]] = None
    """Bot tags."""


class BotUpdate(BaseModel):
    """Schema for updating a bot."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=256)
    """Bot name."""

    description: Optional[str] = Field(default=None, max_length=2000)
    """Bot description."""

    status: Optional[str] = Field(default=None, pattern="^(active|archived|disabled)$")
    """Bot status."""

    visibility: Optional[str] = Field(default=None, pattern="^(private|workspace|tenant|public)$")
    """Bot visibility."""

    tags: Optional[List[str]] = None
    """Bot tags."""


class BotResponse(BaseModel):
    """Bot response schema."""

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


class BotVersionCreate(BaseModel):
    """Schema for creating a bot version."""

    version: Optional[str] = Field(default=None, min_length=1)
    """Optional display version string (stored in metadata)."""

    system_prompt: Optional[str] = Field(default=None, max_length=8000)
    """System prompt."""

    model_ref: Optional[str] = None
    """Model reference."""

    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    """Temperature."""

    max_tokens: Optional[int] = Field(default=None, ge=1)
    """Max tokens."""

    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    """Top-p."""

    tool_refs: Optional[List[str]] = None
    """Allowed tool refs."""

    metadata_json: Optional[Dict[str, Any]] = None
    """Metadata."""

    triggers: Optional[Dict[str, Any]] = None
    """Bot trigger config (webhook/schedule/event)."""

    channels: Optional[Dict[str, Any]] = None
    """Bot channel config (slack/wecom/telegram/email)."""

    limits: Optional[Dict[str, Any]] = None
    """Execution limits."""


class BotVersionUpdate(BaseModel):
    """Schema for updating a draft bot version."""

    system_prompt: Optional[str] = Field(default=None, max_length=8000)
    model_ref: Optional[str] = None
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=1)
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    tool_refs: Optional[List[str]] = None
    metadata_json: Optional[Dict[str, Any]] = None
    triggers: Optional[Dict[str, Any]] = None
    channels: Optional[Dict[str, Any]] = None
    limits: Optional[Dict[str, Any]] = None


class BotVersionResponse(BaseModel):
    """Bot version response schema."""

    id: str
    bot_id: str
    version: str
    status: str
    system_prompt: Optional[str]
    model_ref: Optional[str]
    temperature: Optional[float]
    max_tokens: Optional[int]
    top_p: Optional[float]
    tool_refs: Optional[List[str]]
    metadata_json: Optional[Dict[str, Any]]
    display_version: Optional[str]
    triggers: Optional[Dict[str, Any]]
    channels: Optional[Dict[str, Any]]
    limits: Optional[Dict[str, Any]]
    created_by: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BotPublishRequest(BaseModel):
    """Publish bot version request."""

    version_id: str
    """Version ID to publish."""


class BotExecuteRequest(BaseModel):
    """Execute bot request."""

    messages: Optional[List[ChatMessageInput]] = Field(default=None, min_length=1)
    """Chat messages (manual trigger)."""

    version_id: Optional[str] = None
    """Optional version override."""

    trigger: Literal["manual", "webhook", "schedule", "event"] = "manual"
    """Execution trigger source."""

    event_payload: Optional[Dict[str, Any]] = None
    """Trigger payload for webhook/schedule/event execution."""

    @model_validator(mode="after")
    def validate_inputs(self):
        has_messages = bool(self.messages)
        has_event_payload = self.event_payload is not None
        if not has_messages and not has_event_payload:
            raise ValueError("Either messages or event_payload is required")
        return self


class BotTriggerExecuteRequest(BaseModel):
    """Execute bot from non-manual triggers."""

    version_id: Optional[str] = None
    messages: Optional[List[ChatMessageInput]] = Field(default=None, min_length=1)
    event_payload: Dict[str, Any] = Field(default_factory=dict)


class BotExecuteResponse(BaseModel):
    """Execute bot response."""

    run_id: str
    output: str
    model: str
    tokens_prompt: int = 0
    tokens_completion: int = 0
    finish_reason: Optional[str] = None


class BotMetricsPoint(BaseModel):
    """A single time bucket for bot metrics."""

    bucket: str
    runs_total: int = 0
    runs_succeeded: int = 0
    runs_failed: int = 0
    tokens_prompt: int = 0
    tokens_completion: int = 0
    avg_latency_ms: Optional[int] = None


class BotMetricsResponse(BaseModel):
    """Aggregated bot metrics."""

    runs_total: int = 0
    runs_succeeded: int = 0
    runs_failed: int = 0
    success_rate: float = 0.0
    avg_latency_ms: Optional[int] = None
    tokens_prompt: int = 0
    tokens_completion: int = 0
    active_users: int = 0
    usage_distribution: List[Dict[str, Any]] = Field(default_factory=list)
    resource_usage: Dict[str, Any] = Field(default_factory=dict)
    points: List[BotMetricsPoint] = Field(default_factory=list)


class BotRunLogEntry(BaseModel):
    """Structured bot log row projected from runs/steps."""

    id: str
    run_id: str
    step_id: Optional[str] = None
    level: Literal["info", "warning", "error"] = "info"
    message: str
    code: Optional[str] = None
    status: Optional[str] = None
    created_at: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
