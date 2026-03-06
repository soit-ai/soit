"""models

Secrets domain models.
"""

from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field
from sqlalchemy import Text, Column

from app.kernel.commons.time import utc_now
from app.kernel.commons.ids import generate_secret_id


class Secret(SQLModel, table=True):
    """Secret metadata stored in database (value stored in Vault)."""

    __tablename__ = "secrets"

    id: str = Field(primary_key=True, default_factory=generate_secret_id)
    """Secret ID."""

    tenant_id: str = Field(index=True)
    """Tenant ID."""

    workspace_id: str = Field(index=True)
    """Workspace ID."""

    name: str = Field(index=True, max_length=128)
    """Secret display name."""

    description: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    """Secret description."""

    secret_ref: str = Field(index=True, max_length=256)
    """Secret reference used by tools (e.g., "secret:sec_...")."""

    last_rotated_at: Optional[datetime] = Field(default=None, nullable=True)
    """Last rotation timestamp."""

    created_by: Optional[str] = Field(default=None, nullable=True)
    """User ID who created."""

    updated_by: Optional[str] = Field(default=None, nullable=True)
    """User ID who last updated."""

    deleted_at: Optional[datetime] = Field(default=None, nullable=True)
    """Soft delete timestamp."""

    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""

    updated_at: datetime = Field(default_factory=utc_now)
    """Last update timestamp."""
