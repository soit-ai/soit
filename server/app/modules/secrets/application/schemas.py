"""schemas

Secrets API schemas.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SecretCreate(BaseModel):
    """Create secret request."""

    name: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=1024)
    value: str = Field(min_length=1)


class SecretUpdate(BaseModel):
    """Update secret request."""

    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=1024)
    value: str | None = Field(default=None, min_length=1)


class SecretResponse(BaseModel):
    """Secret response schema (no secret values)."""

    id: str
    name: str
    description: str | None
    last_rotated_at: datetime | None
    created_by: str | None
    updated_by: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SecretTestResponse(BaseModel):
    """Secret test response."""

    ok: bool
    message: str | None = None


class SecretResolutionSummary(BaseModel):
    """How often secrets were handed to governed callers in one window.

    Counted from the audit ledger, which records that a resolution happened and
    never what it resolved to.
    """

    since: datetime | None = None
    until: datetime | None = None
    total: int = 0
    secrets: int = 0
    """Distinct secrets resolved at least once in the window."""
