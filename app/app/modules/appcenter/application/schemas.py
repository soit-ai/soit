""" schemas

AppCenter domain Pydantic schemas.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class AppCreate(BaseModel):
    """App creation schema."""
    
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    icon_url: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    type: Optional[str] = Field(default="WORKFLOW", pattern="^(WORKFLOW|CHAT|BOT|AGENT|DATASET)$")
    status: Optional[str] = Field(default="active", pattern="^(active|archived)$")
    visibility: Optional[str] = Field(default="private", pattern="^(private|workspace|public)$")


class AppUpdate(BaseModel):
    """App update schema."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    icon_url: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    is_public: Optional[bool] = None
    status: Optional[str] = Field(default=None, pattern="^(active|archived)$")
    visibility: Optional[str] = Field(default=None, pattern="^(private|workspace|public)$")


class AppVersionCreate(BaseModel):
    """App version creation schema."""
    
    version: Optional[int] = None
    spec_schema: str = Field(..., min_length=1, max_length=50)
    spec_json: Dict[str, Any]
    status: Optional[str] = Field(default="draft", pattern="^(draft|published|deprecated)$")
    changelog: Optional[str] = Field(None, max_length=5000)


class AppPublish(BaseModel):
    """App publish schema."""
    
    version_id: str
    featured: bool = False


class AppSetCurrentVersion(BaseModel):
    """Set current app version."""

    version_id: str


class AppCloneRequest(BaseModel):
    """Clone app request."""

    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    visibility: Optional[str] = Field(default="private", pattern="^(private|workspace|public)$")
    use_version_id: Optional[str] = None


class AppImportRequest(BaseModel):
    """Import app spec request."""

    name: str = Field(..., min_length=1, max_length=100)
    type: str = Field(default="WORKFLOW", pattern="^(WORKFLOW|CHAT|BOT|AGENT|DATASET)$")
    description: Optional[str] = Field(None, max_length=1000)
    visibility: Optional[str] = Field(default="private", pattern="^(private|workspace|public)$")
    spec_schema: str = Field(..., min_length=1, max_length=50)
    spec_json: Dict[str, Any]
    status: Optional[str] = Field(default="draft", pattern="^(draft|published|deprecated)$")


class AppExportResponse(BaseModel):
    """Export app spec response."""

    format: str
    spec: Any


class AppVersionCompareRequest(BaseModel):
    """Compare two app versions."""

    version_id_a: str
    version_id_b: str


class AppVersionCompareResponse(BaseModel):
    """Compare response."""

    version_id_a: str
    version_id_b: str
    checksum_a: str
    checksum_b: str
    equal: bool
    keys_added: List[str]
    keys_removed: List[str]
    keys_changed: List[str]


class AppInstallRequest(BaseModel):
    """App installation request."""

    version_id: Optional[str] = None


class AppInstallationResponse(BaseModel):
    """App installation response schema."""

    id: str
    tenant_id: str
    workspace_id: str
    app_id: str
    installed_version_id: Optional[str]
    status: str
    installed_by: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AppResponse(BaseModel):
    """App response schema."""
    
    id: str
    tenant_id: str
    workspace_id: str
    type: str
    status: str
    visibility: Optional[str]
    name: str
    description: Optional[str]
    icon_url: Optional[str]
    metadata_json: Optional[Dict[str, Any]]
    current_version_id: Optional[str]
    published_version_id: Optional[str]
    is_public: bool
    category: Optional[str]
    tags: Optional[List[str]]
    created_by: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AppVersionResponse(BaseModel):
    """App version response schema."""
    
    id: str
    tenant_id: str
    workspace_id: str
    app_id: str
    version: int
    status: str
    spec_schema: str
    spec_json: Dict[str, Any]
    changelog: Optional[str]
    created_by: str
    created_at: datetime
    checksum: Optional[str] = None
    created_from_version_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AppMarketResponse(BaseModel):
    """App market response schema."""
    
    id: str
    app_id: str
    tenant_id: str
    workspace_id: str
    published_version_id: str
    downloads_count: int
    rating: Optional[float]
    reviews_count: int
    featured: bool
    published_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AppComponentResponse(BaseModel):
    """App component response schema."""

    id: str
    tenant_id: str
    workspace_id: str
    app_id: str
    app_version_id: str
    component_id: str
    component_type: str
    name: Optional[str]
    spec_json: Dict[str, Any]
    ui_json: Optional[Dict[str, Any]]
    spec_checksum: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AppComponentEdgeResponse(BaseModel):
    """App component edge response schema."""

    id: str
    tenant_id: str
    workspace_id: str
    app_id: str
    app_version_id: str
    edge_id: str
    from_component_id: str
    to_component_id: str
    edge_spec_json: Dict[str, Any]
    spec_checksum: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AppVersionRefResponse(BaseModel):
    """App version ref response schema."""

    id: str
    tenant_id: str
    workspace_id: str
    app_id: str
    app_version_id: str
    ref_type: str
    ref_id: Optional[str]
    ref_key: Optional[str]
    spec_path: Optional[str]
    spec_checksum: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RefImpactResponse(BaseModel):
    """Reference impact response schema."""

    ref_type: str
    ref_id: Optional[str]
    ref_key: Optional[str]
    app_version_ids: List[str]
