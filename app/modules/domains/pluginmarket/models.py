""" models

PluginMarket domain models (Plugin).
"""

from typing import Optional, Dict, Any
from datetime import datetime
from sqlmodel import SQLModel, Field, Column, JSON

from app.kernel.commons.time import utc_now
from app.kernel.commons.ids import generate_ulid


class Plugin(SQLModel, table=True):
    """Plugin model - represents a plugin in the marketplace."""
    
    __tablename__ = "plugins"
    
    id: str = Field(primary_key=True, default_factory=lambda: f"plugin_{generate_ulid()}")
    """Plugin ID."""
    
    tenant_id: str = Field(index=True)
    """Tenant ID."""
    
    workspace_id: str = Field(index=True)
    """Workspace ID."""
    
    name: str = Field()
    """Plugin name."""
    
    version: str = Field()
    """Plugin version."""
    
    description: Optional[str] = Field(default=None, nullable=True)
    """Plugin description."""
    
    spec_json: Dict[str, Any] = Field(sa_column=Column(JSON))
    """Plugin specification (JSON Schema)."""
    
    manifest_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    """Plugin manifest."""
    
    metadata_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    """Plugin metadata."""
    
    published: bool = Field(default=False)
    """Whether plugin is published."""
    
    installed_count: int = Field(default=0)
    """Number of installations."""
    
    created_by: Optional[str] = Field(default=None, nullable=True)
    """Creator user ID."""
    
    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""
    
    updated_at: datetime = Field(default_factory=utc_now)
    """Last update timestamp."""


class PluginInstallation(SQLModel, table=True):
    """PluginInstallation model - represents a plugin installation."""
    
    __tablename__ = "plugin_installations"
    
    id: str = Field(primary_key=True, default_factory=lambda: f"inst_{generate_ulid()}")
    """Installation ID."""
    
    tenant_id: str = Field(index=True)
    """Tenant ID."""
    
    workspace_id: str = Field(index=True)
    """Workspace ID."""
    
    plugin_id: str = Field(foreign_key="plugins.id", index=True)
    """Plugin ID (foreign key)."""
    
    installed_by: Optional[str] = Field(default=None, nullable=True)
    """Installer user ID."""
    
    config_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    """Installation configuration."""
    
    created_at: datetime = Field(default_factory=utc_now)
    """Installation timestamp."""
