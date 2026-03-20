"""Skill application schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class SkillCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=1000)
    category: str = Field(default="tool", min_length=1, max_length=64)
    visibility: str = Field(default="private", pattern="^(private|workspace|tenant)$")
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    spec_json: dict[str, Any] = Field(default_factory=dict)


class SkillUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=1000)
    category: Optional[str] = Field(default=None, min_length=1, max_length=64)
    status: Optional[str] = Field(default=None, pattern="^(active|archived|disabled)$")
    visibility: Optional[str] = Field(default=None, pattern="^(private|workspace|tenant)$")
    metadata_json: Optional[dict[str, Any]] = None


class SkillVersionCreate(BaseModel):
    spec_json: dict[str, Any] = Field(default_factory=dict)


class SkillPublishRequest(BaseModel):
    version_id: str


class SkillResponse(BaseModel):
    id: str
    tenant_id: str
    workspace_id: str
    name: str
    description: Optional[str]
    category: str
    status: str
    visibility: str
    metadata_json: dict[str, Any]
    current_version_id: Optional[str]
    published_version_id: Optional[str]
    created_by: Optional[str]
    updated_by: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SkillVersionResponse(BaseModel):
    id: str
    tenant_id: str
    workspace_id: str
    skill_id: str
    version: int
    status: str
    spec_schema: str
    spec_json: dict[str, Any]
    created_by: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
