""" models

Identity domain DB models (users/tenants/workspaces/memberships).
"""

from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field, Column, UniqueConstraint, Index
from sqlalchemy import Text

from app.kernel.commons.time import utcnow as utc_now
from app.kernel.commons.ids import generate_ulid


def generate_user_id() -> str:
    """Generate user ID."""
    return f"u_{generate_ulid()}"


def generate_tenant_id() -> str:
    """Generate tenant ID."""
    return f"t_{generate_ulid()}"


def generate_workspace_id() -> str:
    """Generate workspace ID."""
    return f"w_{generate_ulid()}"


class User(SQLModel, table=True):
    """User model - global user account."""
    
    __tablename__ = "users"
    
    id: str = Field(primary_key=True, default_factory=generate_user_id)
    """User ID."""
    
    email: str = Field(unique=True, index=True)
    """User email (unique)."""
    
    password_hash: str = Field()
    """Hashed password."""
    
    name: Optional[str] = Field(default=None)
    """User display name."""
    
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
    
    description: Optional[str] = Field(default=None)
    """Workspace description."""
    
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
    """Role (Owner/Admin/Member)."""
    
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
    """Role (Owner/Maintainer/Reader)."""
    
    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""

