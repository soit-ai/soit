""" models

Security domain DB models.
"""

from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field, Column, JSON

from app.kernel.commons.ids import generate_ulid
from app.kernel.commons.time import utc_now


class EgressPolicyAudit(SQLModel, table=True):
    """Audit log for egress policy changes."""

    __tablename__ = "egress_policy_audits"

    id: str = Field(primary_key=True, default_factory=generate_ulid)
    """Audit ID."""

    tenant_id: str = Field(index=True)
    """Tenant ID."""

    workspace_id: Optional[str] = Field(default=None, index=True)
    """Workspace ID (null for tenant-level changes)."""

    scope: str = Field()
    """Scope: tenant or workspace."""

    allowlist: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    """Allowlist snapshot."""

    blocklist: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    """Blocklist snapshot."""

    created_by: Optional[str] = Field(default=None)
    """Actor user ID."""

    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""
