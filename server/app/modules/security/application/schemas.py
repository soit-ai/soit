"""schemas

Security domain schemas.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class EgressPolicyUpdate(BaseModel):
    """Egress policy update payload."""

    allowlist: list[str] = Field(default_factory=list)
    blocklist: list[str] = Field(default_factory=list)


class EgressPolicyResponse(BaseModel):
    """Egress policy response."""

    scope: str
    allowlist: list[str]
    blocklist: list[str]


class EgressPolicyAuditResponse(BaseModel):
    """Egress policy audit response."""

    id: str
    tenant_id: str
    workspace_id: str | None
    scope: str
    allowlist: list[str]
    blocklist: list[str]
    created_by: str | None
    created_at: datetime


class UsagePolicyUpdate(BaseModel):
    """Rate limit and quota update payload."""

    llm_rate_limit_per_minute: int | None = Field(default=None, ge=1)
    tool_rate_limit_per_minute: int | None = Field(default=None, ge=1)
    llm_daily_quota: int | None = Field(default=None, ge=1)
    tool_daily_quota: int | None = Field(default=None, ge=1)


class UsagePolicyResponse(BaseModel):
    """Rate limit and quota response."""

    scope: str
    llm_rate_limit_per_minute: int | None
    tool_rate_limit_per_minute: int | None
    llm_daily_quota: int | None
    tool_daily_quota: int | None
