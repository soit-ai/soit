""" models

Workflow domain DB models (workflow + versions).
"""

from typing import Optional, Dict, Any
from datetime import datetime
from sqlmodel import SQLModel, Field, Column, JSON

from app.kernel.commons.time import utc_now
from app.kernel.commons.ids import generate_workflow_id, generate_workflow_version_id


class Workflow(SQLModel, table=True):
    """Workflow model - workspace-scoped workflow definition."""
    
    __tablename__ = "workflows"
    
    id: str = Field(primary_key=True, default_factory=generate_workflow_id)
    """Workflow ID."""
    
    tenant_id: str = Field(index=True)
    """Tenant ID."""
    
    workspace_id: str = Field(index=True)
    """Workspace ID."""
    
    name: str = Field()
    """Workflow name."""
    
    description: Optional[str] = Field(default=None, nullable=True)
    """Workflow description."""
    
    current_version_id: Optional[str] = Field(default=None, nullable=True)
    """Current version ID (pointer to workflow_versions)."""
    
    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""
    
    updated_at: datetime = Field(default_factory=utc_now)
    """Last update timestamp."""


class WorkflowVersion(SQLModel, table=True):
    """WorkflowVersion model - immutable workflow version."""
    
    __tablename__ = "workflow_versions"
    
    id: str = Field(primary_key=True, default_factory=generate_workflow_version_id)
    """Version ID."""
    
    tenant_id: str = Field(index=True)
    """Tenant ID."""
    
    workspace_id: str = Field(index=True)
    """Workspace ID."""
    
    workflow_id: str = Field(foreign_key="workflows.id", index=True)
    """Workflow ID (foreign key)."""
    
    graph_json: Dict[str, Any] = Field(sa_column=Column(JSON))
    """WorkflowSpec JSON (immutable)."""
    
    created_by: str = Field()
    """User ID who created this version."""
    
    created_at: datetime = Field(default_factory=utc_now, index=True)
    """Creation timestamp."""
