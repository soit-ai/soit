""" models

ModelHub domain models (Model).
"""

from typing import Optional, Dict, Any
from datetime import datetime
from sqlmodel import SQLModel, Field, Column, JSON

from app.kernel.commons.time import utc_now
from app.kernel.commons.ids import generate_ulid


class Model(SQLModel, table=True):
    """Model model - represents a registered LLM model."""
    
    __tablename__ = "models"
    
    id: str = Field(primary_key=True, default_factory=lambda: f"model_{generate_ulid()}")
    """Model ID."""
    
    tenant_id: str = Field(index=True)
    """Tenant ID."""
    
    workspace_id: str = Field(index=True)
    """Workspace ID."""
    
    name: str = Field()
    """Model name."""
    
    provider: str = Field()
    """Provider (openai, anthropic, etc.)."""
    
    model_ref: str = Field()
    """Model reference (e.g., "model:openai:gpt-4")."""
    
    description: Optional[str] = Field(default=None, nullable=True)
    """Model description."""
    
    capabilities_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    """Model capabilities (chat, embed, rerank, etc.)."""
    
    config_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    """Model configuration."""
    
    metadata_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    """Model metadata."""
    
    created_by: Optional[str] = Field(default=None, nullable=True)
    """Creator user ID."""
    
    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""
    
    updated_at: datetime = Field(default_factory=utc_now)
    """Last update timestamp."""
