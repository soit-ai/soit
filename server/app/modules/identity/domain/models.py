""" models

Identity domain DB models (users/tenants/workspaces/memberships).
"""

from datetime import datetime

from sqlmodel import JSON, Column, Field, Index, SQLModel, UniqueConstraint

from app.kernel.commons.ids import generate_ulid
from app.kernel.commons.time import utc_now


def generate_user_id() -> str:
    """Generate user ID."""
    return f"u_{generate_ulid()}"


def generate_tenant_id() -> str:
    """Generate tenant ID."""
    return f"t_{generate_ulid()}"


def generate_workspace_id() -> str:
    """Generate workspace ID."""
    return f"w_{generate_ulid()}"


def generate_resource_grant_id() -> str:
    """Generate resource grant ID."""
    return f"rg_{generate_ulid()}"


class User(SQLModel, table=True):
    """User model - global user account."""

    __tablename__ = "users"

    id: str = Field(primary_key=True, default_factory=generate_user_id)
    """User ID."""

    email: str = Field(unique=True, index=True)
    """User email (unique)."""

    password_hash: str = Field()
    """Hashed password."""

    name: str | None = Field(default=None)
    """User display name."""

    profile_json: dict = Field(default_factory=dict, sa_column=Column(JSON))
    """User profile metadata (avatar, phone, company, etc.)."""

    is_active: bool = Field(default=True)
    """Whether user account is active."""

    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""

    updated_at: datetime = Field(default_factory=utc_now)
    """Last update timestamp."""


class Tenant(SQLModel, table=True):
    """Tenant model - organization/company."""

    __tablename__ = "tenants"

    id: str = Field(primary_key=True, default_factory=generate_tenant_id)
    """Tenant ID."""

    name: str = Field()
    """Tenant name."""

    plan: str = Field(default="free")
    """Tenant plan (free/pro/enterprise)."""

    egress_allowlist: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    """Tenant-level egress allowlist."""

    egress_blocklist: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    """Tenant-level egress blocklist."""

    llm_rate_limit_per_minute: int | None = Field(default=None)
    """Tenant-level LLM rate limit (requests per minute)."""

    tool_rate_limit_per_minute: int | None = Field(default=None)
    """Tenant-level tool rate limit (requests per minute)."""

    llm_daily_quota: int | None = Field(default=None)
    """Tenant-level LLM daily request quota."""

    tool_daily_quota: int | None = Field(default=None)
    """Tenant-level tool daily request quota."""

    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""

    updated_at: datetime = Field(default_factory=utc_now)
    """Last update timestamp."""


class Workspace(SQLModel, table=True):
    """Workspace model - workspace within a tenant."""

    __tablename__ = "workspaces"

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_workspace_tenant_name"),
        Index("idx_workspace_tenant_created", "tenant_id", "created_at"),
    )

    id: str = Field(primary_key=True, default_factory=generate_workspace_id)
    """Workspace ID."""

    tenant_id: str = Field(index=True)
    """Tenant ID (FK to tenants.id)."""

    name: str = Field()
    """Workspace name."""

    description: str | None = Field(default=None)
    """Workspace description."""

    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON))
    """Workspace metadata (team settings, permissions, etc.)."""

    egress_allowlist: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    """Workspace-level egress allowlist."""

    egress_blocklist: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    """Workspace-level egress blocklist."""

    llm_rate_limit_per_minute: int | None = Field(default=None)
    """Workspace-level LLM rate limit (requests per minute)."""

    tool_rate_limit_per_minute: int | None = Field(default=None)
    """Workspace-level tool rate limit (requests per minute)."""

    llm_daily_quota: int | None = Field(default=None)
    """Workspace-level LLM daily request quota."""

    tool_daily_quota: int | None = Field(default=None)
    """Workspace-level tool daily request quota."""

    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""

    updated_at: datetime = Field(default_factory=utc_now)
    """Last update timestamp."""


class TenantMembership(SQLModel, table=True):
    """Tenant membership - user's role in a tenant."""

    __tablename__ = "tenant_memberships"

    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", name="uq_tenant_membership"),
    )

    tenant_id: str = Field(primary_key=True)
    """Tenant ID."""

    user_id: str = Field(primary_key=True)
    """User ID."""

    role: str = Field()
    """Role (Owner/Admin/Dev/Viewer)."""

    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""


class WorkspaceMembership(SQLModel, table=True):
    """Workspace membership - user's role in a workspace."""

    __tablename__ = "workspace_memberships"

    __table_args__ = (
        UniqueConstraint("tenant_id", "workspace_id", "user_id", name="uq_workspace_membership"),
    )

    tenant_id: str = Field(primary_key=True)
    """Tenant ID."""

    workspace_id: str = Field(primary_key=True)
    """Workspace ID."""

    user_id: str = Field(primary_key=True)
    """User ID."""

    role: str = Field()
    """Role (Owner/Admin/Dev/Viewer)."""

    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""


class ApiKey(SQLModel, table=True):
    """API key for programmatic access."""

    __tablename__ = "api_keys"

    id: str = Field(primary_key=True, default_factory=generate_ulid)
    """API key ID."""

    tenant_id: str = Field(index=True)
    """Tenant ID."""

    workspace_id: str = Field(index=True)
    """Workspace ID."""

    user_id: str = Field(index=True)
    """User ID."""

    name: str = Field()
    """Display name."""

    key_prefix: str = Field(index=True)
    """Key prefix for display."""

    key_hash: str = Field(unique=True, index=True)
    """Hash of the full API key."""

    status: str = Field(default="active")
    """Status: active, revoked."""

    last_used_at: datetime | None = Field(default=None)
    """Last used timestamp."""

    revoked_at: datetime | None = Field(default=None)
    """Revoked timestamp."""

    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""

    updated_at: datetime = Field(default_factory=utc_now)
    """Last update timestamp."""
class ResourceGrant(SQLModel, table=True):
    """Resource-level grant for a user."""

    __tablename__ = "resource_grants"

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "workspace_id",
            "resource_type",
            "resource_id",
            "user_id",
            name="uq_resource_grant_scope",
        ),
        Index(
            "idx_resource_grant_resource",
            "tenant_id",
            "workspace_id",
            "resource_type",
            "resource_id",
        ),
        Index(
            "idx_resource_grant_user",
            "tenant_id",
            "workspace_id",
            "user_id",
        ),
    )

    id: str = Field(primary_key=True, default_factory=generate_resource_grant_id)
    """Grant ID."""

    tenant_id: str = Field(index=True)
    """Tenant ID."""

    workspace_id: str = Field(index=True)
    """Workspace ID."""

    resource_type: str = Field(index=True)
    """Resource type."""

    resource_id: str = Field(index=True)
    """Resource ID."""

    user_id: str = Field(index=True)
    """User ID."""

    actions: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    """Allowed actions."""

    created_by: str | None = Field(default=None)
    """User ID that created the grant."""

    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""

    updated_at: datetime = Field(default_factory=utc_now)
    """Last update timestamp."""
