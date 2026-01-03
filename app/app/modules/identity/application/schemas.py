""" schemas

Identity domain Pydantic schemas for API.
"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


# Request schemas
class UserCreate(BaseModel):
    """Schema for creating a user."""
    
    email: EmailStr = Field(..., description="User email")
    password: str = Field(..., min_length=8, description="User password")
    name: Optional[str] = Field(None, description="User display name")


class UserLogin(BaseModel):
    """Schema for user login."""
    
    email: EmailStr = Field(..., description="User email")
    password: str = Field(..., description="User password")


class TenantCreate(BaseModel):
    """Schema for creating a tenant."""
    
    name: str = Field(..., min_length=1, max_length=255, description="Tenant name")
    plan: str = Field(default="free", description="Tenant plan")


class WorkspaceCreate(BaseModel):
    """Schema for creating a workspace."""
    
    name: str = Field(..., min_length=1, max_length=255, description="Workspace name")
    description: Optional[str] = Field(None, description="Workspace description")


class MembershipCreate(BaseModel):
    """Schema for creating a membership."""
    
    user_id: str = Field(..., description="User ID")
    role: str = Field(..., description="Role")


class MembershipUpdate(BaseModel):
    """Schema for updating a membership."""
    
    role: str = Field(..., description="Role")


# Response schemas
class UserResponse(BaseModel):
    """Schema for user response."""
    
    id: str
    email: str
    name: Optional[str]
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class TenantResponse(BaseModel):
    """Schema for tenant response."""
    
    id: str
    name: str
    plan: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class WorkspaceResponse(BaseModel):
    """Schema for workspace response."""
    
    id: str
    tenant_id: str
    name: str
    description: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class MembershipResponse(BaseModel):
    """Schema for membership response."""
    
    tenant_id: Optional[str] = None
    workspace_id: Optional[str] = None
    user_id: str
    role: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """Schema for token response."""
    
    access_token: str
    token_type: str = "bearer"
    expires_in: int

