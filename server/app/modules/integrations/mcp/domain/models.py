"""MCP integration domain models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Index
from sqlmodel import JSON, Column, Field, SQLModel

from app.kernel.commons.ids import generate_ulid
from app.kernel.commons.time import utc_now


def generate_mcp_server_id() -> str:
    return f"mcp_{generate_ulid()}"


class MCPServer(SQLModel, table=True):
    """Registered MCP server connection."""

    __tablename__ = "mcp_servers"
    __table_args__ = (
        Index("ix_mcp_servers_tenant_workspace_enabled", "tenant_id", "workspace_id", "enabled"),
        Index("ix_mcp_servers_tenant_workspace_name", "tenant_id", "workspace_id", "name"),
    )

    id: str = Field(primary_key=True, default_factory=generate_mcp_server_id)
    tenant_id: str = Field(index=True)
    workspace_id: str = Field(index=True)
    name: str = Field(index=True)
    description: Optional[str] = Field(default=None, nullable=True)
    transport: str = Field(default="http", index=True)
    endpoint: str = Field()
    enabled: bool = Field(default=True, index=True)
    status: str = Field(default="active", index=True)
    auth_config_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    capabilities_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    metadata_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_by: Optional[str] = Field(default=None, nullable=True)
    updated_by: Optional[str] = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    deleted_at: Optional[datetime] = Field(default=None, nullable=True)
