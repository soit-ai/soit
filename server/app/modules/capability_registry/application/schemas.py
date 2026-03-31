"""Capability registry application schemas."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class CapabilityResponse(BaseModel):
    """Runtime capability listing item."""

    ref: str
    kind: str
    name: str
    source_kind: str
    source_id: Optional[str] = None
    source_version: Optional[str] = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)
