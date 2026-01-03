""" models

PluginMarket domain persistence models.

Notes
- These are SQLModel tables used by the PluginMarket module.
- Keep this module free of FastAPI / transport concerns.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from sqlmodel import SQLModel, Field, Column, JSON

from app.kernel.commons.ids import generate_ulid
from app.kernel.commons.time import utc_now


class Plugin(SQLModel, table=True):
    """A plugin published to the marketplace (scoped by tenant/workspace)."""

    __tablename__ = "plugins"

    id: str = Field(primary_key=True, default_factory=lambda: f"plg_{generate_ulid()}", index=True)
    tenant_id: str = Field(index=True)
    workspace_id: str = Field(index=True)

    name: str = Field(index=True, min_length=1)
    version: str = Field(index=True, min_length=1)

    description: Optional[str] = Field(default=None, nullable=True)

    # Spec and manifest are stored as JSON blobs (validated at boundaries).
    spec_json: Dict[str, Any] = Field(sa_column=Column(JSON))
    manifest_json: Dict[str, Any] = Field(sa_column=Column(JSON))

    metadata_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    """Arbitrary metadata (e.g. package filename/sha256)."""

    published: bool = Field(default=False, index=True)
    installed_count: int = Field(default=0)

    created_by: Optional[str] = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class PluginInstallation(SQLModel, table=True):
    """A plugin installed into a tenant/workspace environment."""

    __tablename__ = "plugin_installations"

    id: str = Field(primary_key=True, default_factory=lambda: f"inst_{generate_ulid()}", index=True)

    tenant_id: str = Field(index=True)
    workspace_id: str = Field(index=True)

    plugin_id: str = Field(foreign_key="plugins.id", index=True)

    installed_by: Optional[str] = Field(default=None, nullable=True)

    config_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    """Installation configuration; may include enable/disable state."""

    created_at: datetime = Field(default_factory=utc_now)
