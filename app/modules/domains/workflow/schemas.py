""" schemas

Workflow domain schemas.
"""

from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


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


class WorkflowVersionCreate(BaseModel):
    """Schema for creating a workflow version."""
    
    graph_json: Dict[str, Any] = Field(...)
    """WorkflowSpec JSON."""
    
    created_by: str = Field(...)
    """User ID who creates this version."""


class WorkflowResponse(BaseModel):
    """Schema for workflow response."""
    
    id: str
    tenant_id: str
    workspace_id: str
    name: str
    description: Optional[str]
    current_version_id: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class WorkflowVersionResponse(BaseModel):
    """Schema for workflow version response."""
    
    id: str
    tenant_id: str
    workspace_id: str
    workflow_id: str
    graph_json: Dict[str, Any]
    created_by: str
    created_at: datetime
    
    class Config:
        from_attributes = True
