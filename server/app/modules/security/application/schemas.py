"""schemas

Security domain schemas.
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


class EgressPolicyUpdate(BaseModel):
    """Egress policy update payload."""

    allowlist: List[str] = Field(default_factory=list)
    blocklist: List[str] = Field(default_factory=list)


class EgressPolicyResponse(BaseModel):
    """Egress policy response."""

    scope: str
    allowlist: List[str]
    blocklist: List[str]


class EgressPolicyAuditResponse(BaseModel):
    """Egress policy audit response."""

    id: str
    tenant_id: str
    workspace_id: Optional[str]
    scope: str
    allowlist: List[str]
    blocklist: List[str]
    created_by: Optional[str]
    created_at: datetime


class UsagePolicyUpdate(BaseModel):
    """Rate limit and quota update payload."""

    llm_rate_limit_per_minute: Optional[int] = Field(default=None, ge=1)
    tool_rate_limit_per_minute: Optional[int] = Field(default=None, ge=1)
    llm_daily_quota: Optional[int] = Field(default=None, ge=1)
    tool_daily_quota: Optional[int] = Field(default=None, ge=1)


class UsagePolicyResponse(BaseModel):
    """Rate limit and quota response."""

    scope: str
    llm_rate_limit_per_minute: Optional[int]
    tool_rate_limit_per_minute: Optional[int]
    llm_daily_quota: Optional[int]
    tool_daily_quota: Optional[int]
