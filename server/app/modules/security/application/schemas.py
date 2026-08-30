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


class EgressBlockRow(BaseModel):
    """One refused outbound request."""

    id: str
    domain: str | None
    resource_ref: str | None
    reason: str | None
    url: str | None
    actor_user_id: str | None
    trace_id: str | None
    created_at: datetime
    # Which policy content refused this request. Absent for refusals recorded
    # before policy bundles existed, and for the ones decided without a scope
    # policy at all.
    tenant_bundle_id: str | None = None
    workspace_bundle_id: str | None = None


class EgressBlockSummaryResponse(BaseModel):
    """What the egress policy refused inside one window.

    Counted from the audit ledger, so the figure and the evidence behind it are
    the same records. `subjects` counts distinct callers, which is what the
    governance panel means by "1 agent".
    """

    since: datetime | None = None
    until: datetime | None = None
    total: int = 0
    subjects: int = 0
    domains: int = 0
    recent: list[EgressBlockRow] = Field(default_factory=list)


class PolicyDocument(BaseModel):
    """The governed policy of one scope, as a whole.

    Egress rules and usage limits are saved through different endpoints but are
    one policy from a reviewer's point of view: "what was this workspace
    allowed to do" is not two questions. Revisions therefore record both.
    """

    egress_allowlist: list[str] = Field(default_factory=list)
    egress_blocklist: list[str] = Field(default_factory=list)
    llm_rate_limit_per_minute: int | None = None
    tool_rate_limit_per_minute: int | None = None
    llm_daily_quota: int | None = None
    tool_daily_quota: int | None = None


class PolicyBundleResponse(BaseModel):
    """The identifier of the policy currently in force for a scope.

    `revision` is 0 when nothing has been saved since the scope was created:
    the policy is whatever it was installed with, which still has a bundle
    identifier because the identifier is derived from the content.
    """

    scope: str
    scope_id: str
    bundle_id: str
    revision: int = 0
    document: PolicyDocument
    activated_at: datetime | None = None
    activated_by: str | None = None


class PolicyRevisionResponse(BaseModel):
    """One entry in a scope's activation history."""

    id: str
    scope: str
    scope_id: str
    revision: int
    bundle_id: str
    document: PolicyDocument
    note: str | None = None
    restored_from_revision: int | None = None
    created_by: str | None = None
    created_at: datetime
    active: bool = False


class PolicyFieldChange(BaseModel):
    """What one field was, and what it became."""

    field: str
    before: object | None = None
    after: object | None = None


class PolicyRevisionDiff(BaseModel):
    """The difference between two revisions of the same scope.

    An empty `changes` means the two revisions carry the same policy, which is
    possible and worth being able to see: a save that changed nothing still
    happened, and a rollback to identical content is not a no-op in the record.
    """

    scope: str
    from_revision: int
    to_revision: int
    from_bundle_id: str
    to_bundle_id: str
    changes: list[PolicyFieldChange] = Field(default_factory=list)


class PolicyRollbackRequest(BaseModel):
    """Restore a scope to the content of an earlier revision."""

    note: str | None = Field(default=None, max_length=512)
