""" schemas

ModelHub domain schemas.
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel


class ModelCreate(BaseModel):
    """Model creation schema."""
    
    name: str
    """Model name."""
    
    provider: str
    """Provider."""
    
    model_ref: str
    """Model reference."""
    
    description: Optional[str] = None
    """Model description."""
    
    capabilities_json: Optional[Dict[str, Any]] = None
    """Model capabilities."""
    
    config_json: Optional[Dict[str, Any]] = None
    """Model configuration."""
    
    metadata_json: Optional[Dict[str, Any]] = None
    """Model metadata."""


class ModelUpdate(BaseModel):
    """Model update schema."""
    
    name: Optional[str] = None
    """Model name."""
    
    description: Optional[str] = None
    """Model description."""
    
    capabilities_json: Optional[Dict[str, Any]] = None
    """Model capabilities."""
    
    config_json: Optional[Dict[str, Any]] = None
    """Model configuration."""
    
    metadata_json: Optional[Dict[str, Any]] = None
    """Model metadata."""


class ModelResponse(BaseModel):
    """Model response schema."""
    
    id: str
    name: str
    provider: str
    model_ref: str
    description: Optional[str] = None
    capabilities_json: Optional[Dict[str, Any]] = None
    config_json: Optional[Dict[str, Any]] = None
    metadata_json: Optional[Dict[str, Any]] = None
    created_by: Optional[str] = None
    created_at: str
    updated_at: str
    
    class Config:
        from_attributes = True
