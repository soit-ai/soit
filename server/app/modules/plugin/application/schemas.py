"""Plugin application schemas."""

from typing import Optional, Dict, Any, Literal
from datetime import datetime
from pydantic import BaseModel, ConfigDict


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
    
    description: Optional[str] = None
    """Plugin description."""
    
    spec_json: Dict[str, Any]
    """Plugin specification (JSON Schema)."""
    
    manifest_json: Optional[Dict[str, Any]] = None
    """Plugin manifest."""
    
    metadata_json: Optional[Dict[str, Any]] = None
    """Plugin metadata."""


class PluginUpdate(BaseModel):
    """Plugin update schema."""

    model_config = ConfigDict(extra="forbid")
    
    description: Optional[str] = None
    """Plugin description."""

    plugin_type: Optional[Literal["skill", "mcp", "tool", "workflow_node", "mixed"]] = None
    """Plugin type."""

    status: Optional[Literal["active", "disabled", "archived"]] = None
    """Plugin lifecycle status."""
    
    spec_json: Optional[Dict[str, Any]] = None
    """Plugin specification."""
    
    manifest_json: Optional[Dict[str, Any]] = None
    """Plugin manifest."""
    
    metadata_json: Optional[Dict[str, Any]] = None
    """Plugin metadata."""

    publish_status: Optional[str] = None
    """Publish lifecycle status (draft/published/archived)."""


class PluginInstallRequest(BaseModel):
    """Plugin installation request schema."""
    
    config_json: Optional[Dict[str, Any]] = None
    """Installation configuration."""


class PluginResponse(BaseModel):
    """Plugin response schema."""
    
    id: str
    name: str
    version: str
    publisher: str = "soit"
    plugin_type: str = "tool"
    status: str = "active"
    description: Optional[str] = None
    spec_json: Dict[str, Any]
    manifest_json: Optional[Dict[str, Any]] = None
    metadata_json: Optional[Dict[str, Any]] = None
    publish_status: str
    installed_count: int
    current_version_id: Optional[str] = None
    published_version_id: Optional[str] = None
    installed: bool = False
    enabled: Optional[bool] = None
    installation_id: Optional[str] = None
    installed_at: Optional[datetime] = None
    created_by: Optional[str] = None
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
    plugin_version_id: Optional[str] = None
    tenant_id: str
    workspace_id: str
    enabled: bool = True
    state: str = "installed"
    config_json: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class PluginVersionCreate(BaseModel):
    """Create an immutable plugin version from JSON payloads."""

    version: Optional[str] = None
    spec_json: Dict[str, Any]
    manifest_json: Dict[str, Any]
    metadata_json: Optional[Dict[str, Any]] = None


class PluginPublishRequest(BaseModel):
    version_id: str
    notes: Optional[str] = None


class PluginRollbackRequest(BaseModel):
    version_id: str
    notes: Optional[str] = None


class PluginVersionResponse(BaseModel):
    id: str
    plugin_id: str
    tenant_id: str
    workspace_id: str
    version: int
    package_version: str
    status: str
    spec_schema: str
    spec_json: Dict[str, Any]
    manifest_json: Dict[str, Any]
    package_sha256: Optional[str] = None
    artifact_summary_json: Dict[str, Any] = {}
    metadata_json: Dict[str, Any] = {}
    created_by: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PluginReleaseResponse(BaseModel):
    id: str
    plugin_id: str
    version_id: str
    action: str
    scope: str
    status: str
    from_version_id: Optional[str] = None
    to_version_id: Optional[str] = None
    notes: Optional[str] = None
    rollback_of_publish_id: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PluginArtifactResponse(BaseModel):
    id: str
    plugin_id: str
    plugin_version_id: Optional[str] = None
    installation_id: Optional[str] = None
    artifact_kind: str
    artifact_ref: str
    artifact_id: Optional[str] = None
    artifact_version_id: Optional[str] = None
    state: str
    enabled: bool
    metadata_json: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PluginCapabilityResponse(BaseModel):
    ref: str
    kind: str
    name: str
    source_kind: str = "plugin"
    source_id: Optional[str] = None
    source_version: Optional[str] = None
    artifact_kind: Optional[str] = None
    plugin_id: Optional[str] = None
    plugin_version_id: Optional[str] = None
    installation_id: Optional[str] = None
    metadata_json: Dict[str, Any] = {}


class PluginPackageInstallResponse(BaseModel):
    """Response after installing a plugin package to filesystem."""

    install_dir: str
    package_path: str
    manifest_path: str
    spec_path: str


class PluginUpgradeResponse(BaseModel):
    """Response after upgrading a plugin package."""

    plugin: PluginResponse
    install: PluginPackageInstallResponse



class PluginRuntimeReloadResponse(BaseModel):
    loaded_count: int
    loaded: list[dict]


class RuntimeToolListResponse(BaseModel):
    tools: list[dict]
