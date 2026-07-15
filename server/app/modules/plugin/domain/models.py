"""Plugin domain persistence models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlmodel import JSON, Column, Field, SQLModel

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
    publisher: str = Field(default="soit", index=True)
    plugin_type: str = Field(default="tool", index=True)
    status: str = Field(default="active", index=True)

    description: str | None = Field(default=None, nullable=True)

    # Spec and manifest are stored as JSON blobs (validated at boundaries).
    spec_json: dict[str, Any] = Field(sa_column=Column(JSON))
    manifest_json: dict[str, Any] = Field(sa_column=Column(JSON))

    metadata_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    """Arbitrary metadata (e.g. package filename/sha256)."""

    publish_status: str = Field(default="draft", index=True)
    installed_count: int = Field(default=0)
    current_version_id: str | None = Field(default=None, nullable=True, index=True)
    published_version_id: str | None = Field(default=None, nullable=True, index=True)

    created_by: str | None = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class PluginInstallation(SQLModel, table=True):
    """A plugin installed into a tenant/workspace environment."""

    __tablename__ = "plugin_installations"

    id: str = Field(primary_key=True, default_factory=lambda: f"inst_{generate_ulid()}", index=True)

    tenant_id: str = Field(index=True)
    workspace_id: str = Field(index=True)

    plugin_id: str = Field(index=True)
    plugin_version_id: str | None = Field(default=None, index=True)
    enabled: bool = Field(default=True, index=True)
    state: str = Field(default="installed", index=True)

    installed_by: str | None = Field(default=None, nullable=True)

    config_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    """Installation configuration; may include enable/disable state."""

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class PluginVersion(SQLModel, table=True):
    """Immutable plugin package/spec snapshot."""

    __tablename__ = "plugin_versions"

    id: str = Field(primary_key=True, default_factory=lambda: f"plgv_{generate_ulid()}", index=True)
    tenant_id: str = Field(index=True)
    workspace_id: str = Field(index=True)
    plugin_id: str = Field(index=True)
    version: int = Field(index=True)
    package_version: str = Field(index=True)
    status: str = Field(default="draft", index=True)
    spec_schema: str = Field(default="plugin.v1")
    spec_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    manifest_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    package_sha256: str | None = Field(default=None, nullable=True)
    artifact_summary_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    metadata_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_by: str | None = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=utc_now)


class PluginRelease(SQLModel, table=True):
    """Plugin publish/rollback ledger."""

    __tablename__ = "plugin_releases"

    id: str = Field(primary_key=True, default_factory=lambda: f"plgr_{generate_ulid()}", index=True)
    tenant_id: str = Field(index=True)
    workspace_id: str = Field(index=True)
    plugin_id: str = Field(index=True)
    plugin_version_id: str = Field(index=True)
    action: str = Field(default="publish", index=True)
    scope: str = Field(default="workspace")
    status: str = Field(default="published", index=True)
    from_version_id: str | None = Field(default=None, nullable=True)
    to_version_id: str | None = Field(default=None, nullable=True)
    notes: str | None = Field(default=None, nullable=True)
    rollback_of_publish_id: str | None = Field(default=None, nullable=True)
    created_by: str | None = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class PluginInstalledArtifact(SQLModel, table=True):
    """Artifact projected by a plugin installation."""

    __tablename__ = "plugin_installed_artifacts"

    id: str = Field(primary_key=True, default_factory=lambda: f"plga_{generate_ulid()}", index=True)
    tenant_id: str = Field(index=True)
    workspace_id: str = Field(index=True)
    plugin_id: str = Field(index=True)
    plugin_version_id: str | None = Field(default=None, index=True)
    installation_id: str | None = Field(default=None, index=True)
    artifact_kind: str = Field(index=True)
    artifact_ref: str = Field(index=True)
    artifact_id: str | None = Field(default=None, nullable=True, index=True)
    artifact_version_id: str | None = Field(default=None, nullable=True, index=True)
    state: str = Field(default="enabled", index=True)
    enabled: bool = Field(default=True, index=True)
    metadata_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
