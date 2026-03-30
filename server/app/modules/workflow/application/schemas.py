""" schemas

Workflow domain schemas.
"""

from typing import Optional, Dict, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class WorkflowCreate(BaseModel):
    """Schema for creating a workflow."""
    
    name: str = Field(..., min_length=1, max_length=255)
    """Workflow name."""
    
    description: Optional[str] = Field(None, max_length=1000)
    """Workflow description."""

    summary: Optional[str] = Field(None, max_length=1000)
    """Workflow summary for listings."""

    visibility: str = Field(default="private", pattern="^(private|workspace|tenant|public)$")
    """Workflow visibility."""

    icon_url: Optional[str] = Field(None, max_length=2000)
    """Workflow icon URL."""

    category: Optional[str] = Field(None, max_length=128)
    """Workflow category."""

    tags: Optional[list[str]] = None
    """Workflow tags."""


class WorkflowUpdate(BaseModel):
    """Schema for updating a workflow."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    """Workflow name."""
    
    description: Optional[str] = Field(None, max_length=1000)
    """Workflow description."""

    summary: Optional[str] = Field(None, max_length=1000)
    """Workflow summary for listings."""

    status: Optional[str] = Field(None, pattern="^(active|archived|disabled)$")
    """Workflow status."""

    visibility: Optional[str] = Field(None, pattern="^(private|workspace|tenant|public)$")
    """Workflow visibility."""

    icon_url: Optional[str] = Field(None, max_length=2000)
    """Workflow icon URL."""

    category: Optional[str] = Field(None, max_length=128)
    """Workflow category."""

    tags: Optional[list[str]] = None
    """Workflow tags."""

    metadata_json: Optional[Dict[str, Any]] = None
    """Workflow metadata."""


class WorkflowVersionCreate(BaseModel):
    """Schema for creating a workflow version."""
    
    graph_json: Dict[str, Any] = Field(...)
    """WorkflowSpec JSON."""
    
    created_by: str = Field(...)
    """User ID who creates this version."""

    preflight: bool = Field(default=False)
    """Whether to run preflight checks before publish."""


class WorkflowResponse(BaseModel):
    """Schema for workflow response."""
    
    id: str
    tenant_id: str
    workspace_id: str
    name: str
    description: Optional[str]
    summary: Optional[str]
    status: str
    visibility: str
    icon_url: Optional[str]
    category: Optional[str]
    tags: Optional[list[str]]
    owner_user_id: Optional[str]
    current_version_id: Optional[str]
    published_version_id: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class WorkflowVersionResponse(BaseModel):
    """Schema for workflow version response."""
    
    id: str
    tenant_id: str
    workspace_id: str
    workflow_id: str
    graph_json: Dict[str, Any]
    created_by: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class WorkflowReleaseResponse(BaseModel):
    """Schema for workflow release history response."""

    id: str
    workflow_id: str
    version_id: str
    action: str
    scope: str
    status: str
    from_version_id: Optional[str]
    to_version_id: str
    notes: Optional[str]
    rollback_of_publish_id: Optional[str]
    created_by: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkflowDSLImport(BaseModel):
    """Schema for importing workflow DSL."""

    dsl: Union[Dict[str, Any], str] = Field(...)
    """Workflow DSL payload."""

    created_by: str = Field(...)
    """User ID who creates this version."""

    format: str = Field(default="json", pattern="^(json|yaml)$")
    """DSL format."""


class WorkflowPublishRequest(BaseModel):
    """Schema for publishing a workflow version."""

    version_id: str
    """Version ID to publish."""

    preflight: bool = Field(default=False)
    """Whether to run preflight checks before publish."""

    notes: Optional[str] = Field(default=None, max_length=2000)
    """Optional publish notes."""


class WorkflowRollbackRequest(BaseModel):
    """Schema for rolling back a workflow version."""

    version_id: str
    """Target version ID."""

    preflight: bool = Field(default=False)
    """Whether to run preflight checks before rollback."""

    notes: Optional[str] = Field(default=None, max_length=2000)
    """Optional rollback notes."""


class WorkflowDSLExport(BaseModel):
    """Schema for exporting workflow DSL."""

    dsl: Union[Dict[str, Any], str]
    """Workflow DSL payload."""

    format: str = Field(default="json", pattern="^(json|yaml)$")
    """DSL format."""
