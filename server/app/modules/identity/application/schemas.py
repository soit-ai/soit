""" schemas

Identity domain Pydantic schemas for API.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.kernel.identity.api_key_scopes import unknown_scopes


# Request schemas
class UserCreate(BaseModel):
    """Schema for creating a user."""

    email: EmailStr = Field(..., description="User email")
    password: str = Field(..., min_length=8, description="User password")
    name: str | None = Field(None, max_length=255, description="User display name")


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
    description: str | None = Field(None, description="Workspace description")


class MembershipCreate(BaseModel):
    """Schema for creating a membership."""

    user_id: str = Field(..., description="User ID")
    role: str = Field(..., description="Role")


class MembershipUpdate(BaseModel):
    """Schema for updating a membership."""

    role: str = Field(..., description="Role")


class UserProfileUpdate(BaseModel):
    """Schema for updating current user profile."""

    email: EmailStr | None = Field(None, description="User email")
    name: str | None = Field(None, max_length=255, description="User display name")
    profile: dict[str, Any] | None = Field(default=None, description="User profile metadata")


class PasswordChange(BaseModel):
    """Schema for updating user password."""

    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, description="New password")


class WorkspaceUpdate(BaseModel):
    """Schema for updating a workspace."""

    name: str | None = Field(None, min_length=1, max_length=255, description="Workspace name")
    description: str | None = Field(None, description="Workspace description")
    metadata: dict[str, Any] | None = Field(default=None, description="Workspace metadata")
    llm_rate_limit_per_minute: int | None = Field(
        None, ge=0, description="Workspace LLM rate limit per minute (null clears the override)"
    )
    tool_rate_limit_per_minute: int | None = Field(
        None, ge=0, description="Workspace tool rate limit per minute (null clears the override)"
    )
    llm_daily_quota: int | None = Field(
        None, ge=0, description="Workspace LLM daily quota (null clears the override)"
    )
    tool_daily_quota: int | None = Field(
        None, ge=0, description="Workspace tool daily quota (null clears the override)"
    )


# Response schemas
class UserResponse(BaseModel):
    """Schema for user response."""

    id: str
    email: str
    name: str | None
    is_active: bool
    created_at: datetime
    tenant_id: str | None = None
    workspace_id: str | None = None
    tenant_role: str | None = None
    workspace_role: str | None = None
    profile: dict[str, Any] | None = None

    model_config = ConfigDict(from_attributes=True)


class TenantResponse(BaseModel):
    """Schema for tenant response."""

    id: str
    name: str
    plan: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkspaceResponse(BaseModel):
    """Schema for workspace response."""

    id: str
    tenant_id: str
    name: str
    description: str | None
    metadata: dict[str, Any] | None = None
    llm_rate_limit_per_minute: int | None = None
    tool_rate_limit_per_minute: int | None = None
    llm_daily_quota: int | None = None
    tool_daily_quota: int | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MembershipResponse(BaseModel):
    """Schema for membership response."""

    tenant_id: str | None = None
    workspace_id: str | None = None
    user_id: str
    role: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkspaceMemberResponse(BaseModel):
    """Schema for workspace member response."""

    user_id: str
    email: str
    name: str | None
    role: str
    status: str
    created_at: datetime
    last_active_at: datetime | None = None
    """Most recent activity across the member's sessions; None if never seen."""


class MyWorkspaceResponse(BaseModel):
    """A workspace the caller belongs to, and the role they hold in it."""

    id: str
    name: str
    description: str | None = None
    role: str
    created_at: datetime


class SavedViewCreate(BaseModel):
    """Keep a filter under a name."""

    surface: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    query: str = Field(default="", max_length=2048)
    is_default: bool = False


class SavedViewUpdate(BaseModel):
    """Rename a kept filter, repoint it, or make it the default."""

    name: str | None = Field(default=None, min_length=1, max_length=128)
    query: str | None = Field(default=None, max_length=2048)
    is_default: bool | None = None


class SavedViewResponse(BaseModel):
    """A filter someone kept."""

    id: str
    surface: str
    name: str
    query: str
    is_default: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PinCreate(BaseModel):
    """Put an object within reach of every screen."""

    object_type: str = Field(min_length=1, max_length=64)
    object_id: str = Field(min_length=1, max_length=128)
    label: str | None = Field(default=None, max_length=256)


class PinResponse(BaseModel):
    """A pinned object reference."""

    id: str
    object_type: str
    object_id: str
    label: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    """Schema for token response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    workspace_id: str | None = None
    refresh_token: str | None = None
    """Renews the access token without re-entering a password. Shown once."""


class RefreshRequest(BaseModel):
    """Schema for exchanging a refresh token."""

    refresh_token: str = Field(min_length=1)


class UserSessionResponse(BaseModel):
    """One sign-in the user can see and end."""

    id: str
    workspace_id: str | None = None
    status: str
    user_agent: str | None = None
    ip_address: str | None = None
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    current: bool = False
    """True for the session making this request."""

    model_config = ConfigDict(from_attributes=True)


class SessionRevokeAllResponse(BaseModel):
    """How many sessions an all-devices sign-out ended."""

    revoked: int


class ApiKeyCreate(BaseModel):
    """Schema for creating an API key."""

    name: str = Field(..., min_length=1, max_length=255, description="API key name")
    scopes: list[str] = Field(
        ...,
        min_length=1,
        description="Granted scopes (read, write, admin); a ceiling on the key",
    )
    expires_in_days: int = Field(
        ...,
        ge=1,
        le=365,
        description="Lifetime in days; long-lived credentials must be reissued",
    )

    @field_validator("scopes")
    @classmethod
    def _known_scopes(cls, value: list[str]) -> list[str]:
        unknown = unknown_scopes(value)
        if unknown:
            raise ValueError(f"Unknown API key scopes: {', '.join(unknown)}")
        return value


class ApiKeyResponse(BaseModel):
    """Schema for API key response."""

    id: str
    tenant_id: str
    workspace_id: str
    user_id: str
    name: str
    key_prefix: str
    status: str
    scopes: list[str] = Field(default=[], validation_alias="scopes_json")
    expires_at: datetime | None = None
    last_used_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApiKeyCreateResponse(BaseModel):
    """Schema for API key creation response."""

    api_key: str
    item: ApiKeyResponse


class ApiKeyRotateResponse(BaseModel):
    """Schema for API key rotation response."""

    api_key: str
    item: ApiKeyResponse


class ResourceGrantCreate(BaseModel):
    """Schema for creating a resource grant."""

    resource_type: str = Field(..., description="Resource type")
    resource_id: str = Field(..., description="Resource ID")
    user_id: str = Field(..., description="User ID")
    actions: list[str] = Field(default_factory=list, description="Allowed actions")


class ResourceGrantResponse(BaseModel):
    """Schema for resource grant response."""

    id: str
    tenant_id: str
    workspace_id: str
    resource_type: str
    resource_id: str
    user_id: str
    actions: list[str]
    created_by: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
