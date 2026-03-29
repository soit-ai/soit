"""Plugin application schemas."""

from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class PluginCreate(BaseModel):
    """Plugin creation schema."""
    
    name: str
    """Plugin name."""
    
    version: str
    """Plugin version."""
    
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
    
    description: Optional[str] = None
    """Plugin description."""
    
    spec_json: Optional[Dict[str, Any]] = None
    """Plugin specification."""
    
    manifest_json: Optional[Dict[str, Any]] = None
    """Plugin manifest."""
    
    metadata_json: Optional[Dict[str, Any]] = None
    """Plugin metadata."""

    publish_status: Optional[str] = None
    """Publish lifecycle status (draft/published/archived)."""

    published: Optional[bool] = None
    """Compatibility alias for publish_status."""


class PluginInstallRequest(BaseModel):
    """Plugin installation request schema."""
    
    config_json: Optional[Dict[str, Any]] = None
    """Installation configuration."""


class PluginResponse(BaseModel):
    """Plugin response schema."""
    
    id: str
    name: str
    version: str
    description: Optional[str] = None
    spec_json: Dict[str, Any]
    manifest_json: Optional[Dict[str, Any]] = None
    metadata_json: Optional[Dict[str, Any]] = None
    publish_status: str
    published: bool
    installed_count: int
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
    tenant_id: str
    workspace_id: str
    config_json: Optional[Dict[str, Any]] = None
    created_at: datetime


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
