"""schemas

Secrets API schemas.
"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class SecretCreate(BaseModel):
    """Create secret request."""

    name: str = Field(min_length=1, max_length=128)
    description: Optional[str] = Field(default=None, max_length=1024)
    value: str = Field(min_length=1)


class SecretUpdate(BaseModel):
    """Update secret request."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    description: Optional[str] = Field(default=None, max_length=1024)
    value: Optional[str] = Field(default=None, min_length=1)


class SecretResponse(BaseModel):
    """Secret response schema (no secret values)."""

    id: str
    name: str
    description: Optional[str]
    secret_ref: str
    last_rotated_at: Optional[datetime]
    created_by: Optional[str]
    updated_by: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SecretTestResponse(BaseModel):
    """Secret test response."""

    ok: bool
    message: Optional[str] = None
