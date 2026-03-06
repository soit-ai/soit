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


class WorkflowUpdate(BaseModel):
    """Schema for updating a workflow."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    """Workflow name."""
    
    description: Optional[str] = Field(None, max_length=1000)
    """Workflow description."""

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
    current_version_id: Optional[str]
    metadata_json: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    
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


class WorkflowDSLExport(BaseModel):
    """Schema for exporting workflow DSL."""

    dsl: Union[Dict[str, Any], str]
    """Workflow DSL payload."""

    format: str = Field(default="json", pattern="^(json|yaml)$")
    """DSL format."""
