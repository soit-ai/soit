""" schemas

PluginMarket domain schemas.
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel


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
    
    published: Optional[bool] = None
    """Whether plugin is published."""


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
    published: bool
    installed_count: int
    created_by: Optional[str] = None
    created_at: str
    updated_at: str
    
    class Config:
        from_attributes = True
