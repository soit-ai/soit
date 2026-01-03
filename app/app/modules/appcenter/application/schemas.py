""" schemas

AppCenter domain Pydantic schemas.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field


class AppCreate(BaseModel):
    """App creation schema."""
    
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    icon_url: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None


class AppUpdate(BaseModel):
    """App update schema."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    icon_url: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    is_public: Optional[bool] = None


class AppVersionCreate(BaseModel):
    """App version creation schema."""
    
    version: str = Field(..., min_length=1, max_length=50)
    manifest_json: Dict[str, Any]
    workflow_version_id: Optional[str] = None
    changelog: Optional[str] = Field(None, max_length=5000)


class AppPublish(BaseModel):
    """App publish schema."""
    
    version_id: str
    featured: bool = False


class AppResponse(BaseModel):
    """App response schema."""
    
    id: str
    tenant_id: str
    workspace_id: str
    name: str
    description: Optional[str]
    icon_url: Optional[str]
    current_version_id: Optional[str]
    published_version_id: Optional[str]
    is_public: bool
    category: Optional[str]
    tags: Optional[List[str]]
    created_by: str
    created_at: datetime
    updated_at: datetime


class AppVersionResponse(BaseModel):
    """App version response schema."""
    
    id: str
    tenant_id: str
    workspace_id: str
    app_id: str
    version: str
    manifest_json: Dict[str, Any]
    workflow_version_id: Optional[str]
    changelog: Optional[str]
    created_by: str
    created_at: datetime


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

