"""Plugin application schemas."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class PluginCreate(BaseModel):
    """Plugin creation schema."""

    name: str
    """Plugin name."""

    version: str
    """Plugin version."""

    publisher: str = "soit"
    """Plugin publisher."""

    plugin_type: Literal["skill", "mcp", "tool", "workflow_node", "mixed"] = "tool"
    """Plugin type used by the unified plugin query API."""

    description: str | None = None
    """Plugin description."""

    spec_json: dict[str, Any]
    """Plugin specification (JSON Schema)."""

    manifest_json: dict[str, Any] | None = None
    """Plugin manifest."""

    metadata_json: dict[str, Any] | None = None
    """Plugin metadata."""


class PluginUpdate(BaseModel):
    """Plugin update schema."""

    model_config = ConfigDict(extra="forbid")

    description: str | None = None
    """Plugin description."""

    plugin_type: Literal["skill", "mcp", "tool", "workflow_node", "mixed"] | None = None
    """Plugin type."""

    status: Literal["active", "disabled", "archived"] | None = None
    """Plugin lifecycle status."""

    spec_json: dict[str, Any] | None = None
    """Plugin specification."""

    manifest_json: dict[str, Any] | None = None
    """Plugin manifest."""

    metadata_json: dict[str, Any] | None = None
    """Plugin metadata."""

    publish_status: str | None = None
    """Publish lifecycle status (draft/published/archived)."""


class PluginInstallRequest(BaseModel):
    """Plugin installation request schema."""

    config_json: dict[str, Any] | None = None
    """Installation configuration."""


class PluginResponse(BaseModel):
    """Plugin response schema."""

    id: str
    name: str
    version: str
    publisher: str = "soit"
    plugin_type: str = "tool"
    status: str = "active"
    description: str | None = None
    spec_json: dict[str, Any]
    manifest_json: dict[str, Any] | None = None
    metadata_json: dict[str, Any] | None = None
    publish_status: str
    installed_count: int
    current_version_id: str | None = None
    published_version_id: str | None = None
    installed: bool = False
    enabled: bool | None = None
    installation_id: str | None = None
    installed_at: datetime | None = None
    risk_level: str = "low"
    """Derived from the permissions the plugin declares, never stored."""

    risk_reasons: list[str] = Field(default_factory=list)
    """The declared scopes that produced the level, for display."""

    update_available: bool = False
    """True when this installation is pinned behind the published version."""

    installed_version_id: str | None = None
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PluginEnableRequest(BaseModel):
    """Enable/disable request."""

    enabled: bool


class PluginInstallationResponse(BaseModel):
    """Plugin installation response."""

    id: str
    plugin_id: str
    plugin_version_id: str | None = None
    tenant_id: str
    workspace_id: str
    enabled: bool = True
    state: str = "installed"
    config_json: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class PluginVersionCreate(BaseModel):
    """Create an immutable plugin version from JSON payloads."""

    version: str | None = None
    spec_json: dict[str, Any]
    manifest_json: dict[str, Any]
    metadata_json: dict[str, Any] | None = None


class PluginPublishRequest(BaseModel):
    version_id: str
    notes: str | None = None


class PluginRollbackRequest(BaseModel):
    version_id: str
    notes: str | None = None


class PluginVersionResponse(BaseModel):
    id: str
    plugin_id: str
    tenant_id: str
    workspace_id: str
    version: int
    package_version: str
    status: str
    spec_schema: str
    spec_json: dict[str, Any]
    manifest_json: dict[str, Any]
    package_sha256: str | None = None
    artifact_summary_json: dict[str, Any] = {}
    metadata_json: dict[str, Any] = {}
    created_by: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PluginReleaseResponse(BaseModel):
    id: str
    plugin_id: str
    version_id: str
    action: str
    scope: str
    status: str
    from_version_id: str | None = None
    to_version_id: str | None = None
    notes: str | None = None
    rollback_of_publish_id: str | None = None
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PluginArtifactResponse(BaseModel):
    id: str
    plugin_id: str
    plugin_version_id: str | None = None
    installation_id: str | None = None
    artifact_kind: str
    artifact_ref: str
    artifact_id: str | None = None
    artifact_version_id: str | None = None
    state: str
    enabled: bool
    metadata_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PluginCapabilityResponse(BaseModel):
    ref: str
    kind: str
    name: str
    source_kind: str = "plugin"
    source_id: str | None = None
    source_version: str | None = None
    artifact_kind: str | None = None
    plugin_id: str | None = None
    plugin_version_id: str | None = None
    installation_id: str | None = None
    metadata_json: dict[str, Any] = {}


class PluginPackageInstallResponse(BaseModel):
    """Response after installing a plugin package to filesystem."""

    install_dir: str
    package_path: str
    manifest_path: str
    spec_path: str


class PluginPackageUploadResponse(BaseModel):
    """Response after one-click plugin package upload."""

    action: Literal["created", "upgraded", "reinstalled"]
    plugin: PluginResponse
    install: PluginPackageInstallResponse


class PluginUpgradeResponse(BaseModel):
    """Response after upgrading a plugin package."""

    plugin: PluginResponse
    install: PluginPackageInstallResponse



class PluginRuntimeReloadResponse(BaseModel):
    loaded_count: int
    loaded: list[dict]


class RuntimeToolListResponse(BaseModel):
    tools: list[dict]
