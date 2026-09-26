""" schemas

Identity domain Pydantic schemas for API.
"""

import ipaddress
from datetime import datetime
from typing import Any, Literal

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
    require_mfa: bool | None = Field(
        None, description="Require a confirmed second factor to reach this workspace"
    )
    content_capture: Literal["full", "metadata_only"] | None = Field(
        None,
        description="What runs record of content; metadata_only keeps only lengths and hashes",
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
    require_mfa: bool = False
    content_capture: str = "full"
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

    mfa_enabled: bool = False
    """Whether this member has confirmed a second factor."""


class MyWorkspaceResponse(BaseModel):
    """A workspace the caller belongs to, and the role they hold in it."""

    id: str
    name: str
    description: str | None = None
    role: str
    created_at: datetime


class PasswordResetRequest(BaseModel):
    """Ask for a reset link."""

    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Set a new password from a link."""

    token: str = Field(min_length=1)
    new_password: str = Field(min_length=8)


class EmailVerificationConfirm(BaseModel):
    """Confirm an address from a link."""

    token: str = Field(min_length=1)


class InvitationCreate(BaseModel):
    """Offer membership to an address."""

    email: EmailStr
    role: str = Field(min_length=1, max_length=32)


class InvitationAccept(BaseModel):
    """Redeem an invitation as the signed-in account."""

    token: str = Field(min_length=1)


class InvitationResponse(BaseModel):
    """A pending or closed offer of membership."""

    id: str
    workspace_id: str
    email: str
    role: str
    status: str
    invited_by: str | None = None
    expires_at: datetime
    accepted_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MailCapabilityResponse(BaseModel):
    """Whether this deployment can send its own mail.

    The console asks before offering a reset or an invitation, so it can say
    the feature is unavailable rather than take a request nothing will act on.
    """

    mail_enabled: bool


class AccountDeletionRequestCreate(BaseModel):
    """Why the account is being closed. Optional, and kept for the audit."""

    reason: str | None = Field(default=None, max_length=512)


class AccountDeletionRequestResponse(BaseModel):
    """A pending closure and when it takes effect."""

    id: str
    status: str
    reason: str | None = None
    requested_at: datetime
    execute_after: datetime
    cancelled_at: datetime | None = None
    executed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class MfaStatusResponse(BaseModel):
    """Whether a second factor is set up, and how much of it is left."""

    enabled: bool
    pending: bool = False
    confirmed_at: datetime | None = None
    last_used_at: datetime | None = None
    recovery_codes_remaining: int = 0


class MfaSetupResponse(BaseModel):
    """Everything needed to enrol an authenticator. Shown once."""

    secret: str
    provisioning_uri: str


class MfaConfirmRequest(BaseModel):
    """The code proving the authenticator holds the secret."""

    code: str = Field(min_length=1, max_length=32)


class MfaDisableRequest(BaseModel):
    """Password, because a live session alone must not drop the second factor."""

    password: str = Field(min_length=1)


class MfaRecoveryCodesResponse(BaseModel):
    """Single-use codes, returned once and stored only as hashes."""

    recovery_codes: list[str]


class MfaChallengeResponse(BaseModel):
    """A sign-in that stopped at the second factor."""

    mfa_required: bool = True
    mfa_token: str
    expires_in: int


class MfaLoginRequest(BaseModel):
    """Completing a sign-in with the code, or with a recovery code."""

    mfa_token: str = Field(min_length=1)
    code: str = Field(min_length=1, max_length=32)


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


MAX_API_KEY_ALLOWLIST_ENTRIES = 64
MAX_API_KEY_ALLOWED_MODELS = 256


def _normalized_networks(value: list[str] | None) -> list[str] | None:
    """Canonical CIDR strings for an allowlist, or None for "any address"."""
    if value is None:
        return None
    if not value:
        raise ValueError("An empty IP allowlist admits nobody; use null to allow any address")
    networks: list[str] = []
    for entry in value:
        try:
            networks.append(str(ipaddress.ip_network(entry.strip(), strict=False)))
        except ValueError as exc:
            raise ValueError(f"Not an IP address or CIDR range: {entry}") from exc
    return sorted(set(networks))


def _normalized_models(value: list[str] | None) -> list[str] | None:
    """Distinct model refs, or None for "every model"."""
    if value is None:
        return None
    models = sorted({entry.strip() for entry in value if entry.strip()})
    if not models:
        raise ValueError("An empty model list allows no model; use null to allow every model")
    if any(len(model) > 512 for model in models):
        raise ValueError("Model refs are at most 512 characters")
    return models


class ApiKeyLimits(BaseModel):
    """What a key may do beyond its scopes; every null means "no limit"."""

    rate_limit_per_minute: int | None = Field(default=None, ge=1, le=1_000_000)
    daily_request_quota: int | None = Field(default=None, ge=1)
    daily_token_quota: int | None = Field(default=None, ge=1)
    ip_allowlist: list[str] | None = Field(
        default=None,
        max_length=MAX_API_KEY_ALLOWLIST_ENTRIES,
        description="Addresses or CIDR ranges the key is accepted from",
    )
    allowed_models: list[str] | None = Field(
        default=None,
        max_length=MAX_API_KEY_ALLOWED_MODELS,
        description="Model refs the key may call",
    )
    content_capture: Literal["metadata_only"] | None = Field(
        default=None,
        description="metadata_only keeps this key's calls out of run text; null follows the workspace",
    )

    @field_validator("ip_allowlist")
    @classmethod
    def _valid_allowlist(cls, value: list[str] | None) -> list[str] | None:
        return _normalized_networks(value)

    @field_validator("allowed_models")
    @classmethod
    def _valid_models(cls, value: list[str] | None) -> list[str] | None:
        return _normalized_models(value)


class ApiKeyCreate(ApiKeyLimits):
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
    principal_id: str | None = Field(
        default=None,
        description="Issue the key to a service principal, which it then authenticates as",
    )

    @field_validator("scopes")
    @classmethod
    def _known_scopes(cls, value: list[str]) -> list[str]:
        unknown = unknown_scopes(value)
        if unknown:
            raise ValueError(f"Unknown API key scopes: {', '.join(unknown)}")
        return value


class ApiKeyUpdate(ApiKeyLimits):
    """A change to a key's name or limits; only the fields sent are changed.

    Sending a limit as null removes it. Scopes and expiry are not editable:
    widening either takes a new key.
    """

    name: str | None = Field(default=None, min_length=1, max_length=255)


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
    rate_limit_per_minute: int | None = None
    daily_request_quota: int | None = None
    daily_token_quota: int | None = None
    ip_allowlist: list[str] | None = Field(default=None, validation_alias="ip_allowlist_json")
    allowed_models: list[str] | None = Field(default=None, validation_alias="allowed_models_json")
    content_capture: str | None = None
    principal_id: str | None = None
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

class ServicePrincipalCreate(BaseModel):
    """A non-human caller of this workspace."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    workspace_role: Literal["Viewer", "Dev", "Admin"] = "Dev"
    owner_user_id: str | None = Field(
        default=None,
        description="Member accountable for it; defaults to the creator",
    )


class ServicePrincipalUpdate(BaseModel):
    """A change to a service principal; only the fields sent are changed."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    workspace_role: Literal["Viewer", "Dev", "Admin"] | None = None
    owner_user_id: str | None = None
    status: Literal["active", "disabled"] | None = None


class ServicePrincipalResponse(BaseModel):
    id: str
    tenant_id: str
    workspace_id: str
    name: str
    description: str | None = None
    owner_user_id: str
    workspace_role: str
    status: str
    created_by: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
