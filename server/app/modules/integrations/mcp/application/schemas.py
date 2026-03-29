"""MCP application schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class MCPServerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=1000)
    transport: str = Field(default="http", min_length=1, max_length=64)
    endpoint: str
    status: str = Field(default="active", pattern="^(active|archived|disabled)$")
    enabled: Optional[bool] = None
    auth_config_json: dict[str, Any] = Field(default_factory=dict)
    capabilities_json: dict[str, Any] = Field(default_factory=dict)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class MCPServerUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=1000)
    transport: Optional[str] = Field(default=None, min_length=1, max_length=64)
    endpoint: Optional[str] = None
    enabled: Optional[bool] = None
    status: Optional[str] = Field(default=None, pattern="^(active|archived|disabled)$")
    auth_config_json: Optional[dict[str, Any]] = None
    capabilities_json: Optional[dict[str, Any]] = None
    metadata_json: Optional[dict[str, Any]] = None


class MCPServerResponse(BaseModel):
    id: str
    tenant_id: str
    workspace_id: str
    name: str
    description: Optional[str]
    transport: str
    endpoint: str
    enabled: bool
    status: str
    auth_config_json: dict[str, Any]
    capabilities_json: dict[str, Any]
    metadata_json: dict[str, Any]
    created_by: Optional[str]
    updated_by: Optional[str]
    created_at: datetime
    updated_at: datetime
    binding_type: str
    binding_ref: str
    server_ref: str

    model_config = ConfigDict(from_attributes=True)


class MCPBindingTargetResponse(BaseModel):
    binding_type: str
    binding_ref: str
    server_ref: str
    server_id: str
    server_name: str
    capability_key: Optional[str] = None
    capability_name: Optional[str] = None
    description: Optional[str] = None
    uri: Optional[str] = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class MCPCatalogResponse(BaseModel):
    tools: list[dict[str, Any]]
    resources: list[dict[str, Any]]
    templates: list[dict[str, Any]]
