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
    secret_ref: str
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
