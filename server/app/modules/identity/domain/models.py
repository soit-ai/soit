""" models

Identity domain DB models (users/tenants/workspaces/memberships).
"""

from datetime import datetime

from sqlalchemy import DateTime, PrimaryKeyConstraint
from sqlmodel import JSON, Column, Field, Index, SQLModel, UniqueConstraint

from app.kernel.commons.ids import generate_ulid
from app.kernel.commons.time import utc_now


def generate_user_id() -> str:
    """Generate user ID."""
    return f"u_{generate_ulid()}"


def generate_tenant_id() -> str:
    """Generate tenant ID."""
    return f"t_{generate_ulid()}"


def generate_workspace_id() -> str:
    """Generate workspace ID."""
    return f"w_{generate_ulid()}"


def generate_resource_grant_id() -> str:
    """Generate resource grant ID."""
    return f"rg_{generate_ulid()}"


def generate_user_session_id() -> str:
    """Generate user session ID."""
    return f"ses_{generate_ulid()}"


def generate_identity_token_id() -> str:
    """Generate identity token ID."""
    return f"itk_{generate_ulid()}"


def generate_invitation_id() -> str:
    """Generate workspace invitation ID."""
    return f"inv_{generate_ulid()}"


def generate_deletion_request_id() -> str:
    """Generate account deletion request ID."""
    return f"adr_{generate_ulid()}"


def generate_user_mfa_id() -> str:
    """Generate MFA enrolment ID."""
    return f"mfa_{generate_ulid()}"


def generate_saved_view_id() -> str:
    """Generate saved view ID."""
    return f"sv_{generate_ulid()}"


def generate_pin_id() -> str:
    """Generate pinned object ID."""
    return f"pin_{generate_ulid()}"


class User(SQLModel, table=True):
    """User model - global user account."""

    __tablename__ = "users"

    id: str = Field(primary_key=True, default_factory=generate_user_id)
    """User ID."""

    email: str = Field(unique=True, index=True)
    """User email (unique)."""

    password_hash: str = Field()
    """Hashed password."""

    name: str | None = Field(default=None)
    """User display name."""

    profile_json: dict = Field(default_factory=dict, sa_column=Column(JSON))
    """User profile metadata (avatar, phone, company, etc.)."""

    is_active: bool = Field(default=True)
    """Whether user account is active."""

    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""

    updated_at: datetime = Field(default_factory=utc_now)
    """Last update timestamp."""


class Tenant(SQLModel, table=True):
    """Tenant model - organization/company."""

    __tablename__ = "tenants"

    id: str = Field(primary_key=True, default_factory=generate_tenant_id)
    """Tenant ID."""

    name: str = Field()
    """Tenant name."""

    plan: str = Field(default="free")
    """Tenant plan (free/pro/enterprise)."""

    egress_allowlist: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    """Tenant-level egress allowlist."""

    egress_blocklist: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    """Tenant-level egress blocklist."""

    llm_rate_limit_per_minute: int | None = Field(default=None)
    """Tenant-level LLM rate limit (requests per minute)."""

    tool_rate_limit_per_minute: int | None = Field(default=None)
    """Tenant-level tool rate limit (requests per minute)."""

    llm_daily_quota: int | None = Field(default=None)
    """Tenant-level LLM daily request quota."""

    tool_daily_quota: int | None = Field(default=None)
    """Tenant-level tool daily request quota."""

    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""

    updated_at: datetime = Field(default_factory=utc_now)
    """Last update timestamp."""


class Workspace(SQLModel, table=True):
    """Workspace model - workspace within a tenant."""

    __tablename__ = "workspaces"

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_workspace_tenant_name"),
        Index("idx_workspace_tenant_created", "tenant_id", "created_at"),
    )

    id: str = Field(primary_key=True, default_factory=generate_workspace_id)
    """Workspace ID."""

    tenant_id: str = Field(index=True)
    """Tenant ID (FK to tenants.id)."""

    name: str = Field()
    """Workspace name."""

    description: str | None = Field(default=None)
    """Workspace description."""

    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON))
    """Workspace metadata (team settings, permissions, etc.)."""

    egress_allowlist: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    """Workspace-level egress allowlist."""

    egress_blocklist: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    """Workspace-level egress blocklist."""

    llm_rate_limit_per_minute: int | None = Field(default=None)
    """Workspace-level LLM rate limit (requests per minute)."""

    tool_rate_limit_per_minute: int | None = Field(default=None)
    """Workspace-level tool rate limit (requests per minute)."""

    llm_daily_quota: int | None = Field(default=None)
    """Workspace-level LLM daily request quota."""

    tool_daily_quota: int | None = Field(default=None)
    """Workspace-level tool daily request quota."""

    require_mfa: bool = Field(default=False)
    """Members without a confirmed second factor cannot reach this workspace.

    Enforced at access resolution rather than at sign-in: the requirement
    belongs to one workspace, and a person may hold others that do not ask for
    it. Turning it on locks out members who have not enrolled yet, which is the
    intent -- they enrol and come back.
    """

    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""

    updated_at: datetime = Field(default_factory=utc_now)
    """Last update timestamp."""


class TenantMembership(SQLModel, table=True):
    """Tenant membership - user's role in a tenant."""

    __tablename__ = "tenant_memberships"

    __table_args__ = (
        PrimaryKeyConstraint("tenant_id", "user_id", name="uq_tenant_membership"),
    )

    tenant_id: str = Field(primary_key=True)
    """Tenant ID."""

    user_id: str = Field(primary_key=True)
    """User ID."""

    role: str = Field()
    """Role (Owner/Admin/Dev/Viewer)."""

    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""


class WorkspaceMembership(SQLModel, table=True):
    """Workspace membership - user's role in a workspace."""

    __tablename__ = "workspace_memberships"

    __table_args__ = (
        PrimaryKeyConstraint(
            "tenant_id",
            "workspace_id",
            "user_id",
            name="uq_workspace_membership",
        ),
    )

    tenant_id: str = Field(primary_key=True)
    """Tenant ID."""

    workspace_id: str = Field(primary_key=True)
    """Workspace ID."""

    user_id: str = Field(primary_key=True)
    """User ID."""

    role: str = Field()
    """Role (Owner/Admin/Dev/Viewer)."""

    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""


class ApiKey(SQLModel, table=True):
    """API key for programmatic access."""

    __tablename__ = "api_keys"

    id: str = Field(primary_key=True, default_factory=generate_ulid)
    """API key ID."""

    tenant_id: str = Field(index=True)
    """Tenant ID."""

    workspace_id: str = Field(index=True)
    """Workspace ID."""

    user_id: str = Field(index=True)
    """User ID."""

    name: str = Field()
    """Display name."""

    key_prefix: str = Field(index=True)
    """Key prefix for display."""

    key_hash: str = Field(unique=True, index=True)
    """Hash of the full API key."""

    status: str = Field(default="active")
    """Status: active, revoked."""

    scopes_json: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    """Granted scopes; a ceiling on what this key may do."""

    expires_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True, index=True),
    )
    """Expiry; requests presenting the key after this moment are rejected."""

    last_used_at: datetime | None = Field(default=None)
    """Last used timestamp."""

    revoked_at: datetime | None = Field(default=None)
    """Revoked timestamp."""

    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""

    updated_at: datetime = Field(default_factory=utc_now)
    """Last update timestamp."""
class ResourceGrant(SQLModel, table=True):
    """Resource-level grant for a user."""

    __tablename__ = "resource_grants"

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "workspace_id",
            "resource_type",
            "resource_id",
            "user_id",
            name="uq_resource_grant_scope",
        ),
        Index(
            "idx_resource_grant_resource",
            "tenant_id",
            "workspace_id",
            "resource_type",
            "resource_id",
        ),
        Index(
            "idx_resource_grant_user",
            "tenant_id",
            "workspace_id",
            "user_id",
        ),
    )

    id: str = Field(primary_key=True, default_factory=generate_resource_grant_id)
    """Grant ID."""

    tenant_id: str = Field(index=True)
    """Tenant ID."""

    workspace_id: str = Field(index=True)
    """Workspace ID."""

    resource_type: str = Field(index=True)
    """Resource type."""

    resource_id: str = Field(index=True)
    """Resource ID."""

    user_id: str = Field(index=True)
    """User ID."""

    actions: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    """Allowed actions."""

    created_by: str | None = Field(default=None)
    """User ID that created the grant."""

    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""

    updated_at: datetime = Field(default_factory=utc_now)
    """Last update timestamp."""


class UserSession(SQLModel, table=True):
    """One sign-in, and the refresh credential that keeps it alive.

    A session is what a person can see and end. The access token names it, so
    ending the session ends the access it granted rather than waiting for a
    token nobody can find to expire.

    Only the hash of the refresh token is stored: the credential itself is
    handed to the client once and never again, the same rule API keys follow.
    """

    __tablename__ = "user_sessions"
    __table_args__ = (
        Index("ix_user_sessions_user_status", "user_id", "status"),
        Index("ix_user_sessions_expiry", "status", "expires_at"),
    )

    id: str = Field(primary_key=True, default_factory=generate_user_session_id)
    tenant_id: str = Field(index=True)
    user_id: str = Field(index=True)
    workspace_id: str | None = Field(default=None, nullable=True, index=True)
    """Workspace the session signed in to; a switch does not start a new one."""

    refresh_token_hash: str = Field(unique=True, index=True)
    """SHA-256 of the current refresh token. Rotated on every refresh."""

    status: str = Field(default="active", index=True)
    """active, revoked or expired."""

    user_agent: str | None = Field(default=None, nullable=True, max_length=512)
    ip_address: str | None = Field(default=None, nullable=True, max_length=64)

    created_at: datetime = Field(default_factory=utc_now)
    last_seen_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
    )
    """Updated on refresh, which is the only moment the server hears from it."""

    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
    )
    revoked_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    revoked_by: str | None = Field(default=None, nullable=True)
    """Who ended it: the user themselves, or an admin."""


class SavedView(SQLModel, table=True):
    """A filter someone kept, so they do not rebuild it every morning.

    The query is stored as the console's own query string rather than parsed
    into columns: the filters a screen offers change with the screen, and a
    schema here would have to be migrated every time one did.
    """

    __tablename__ = "saved_views"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "user_id",
            "surface",
            "name",
            name="uq_saved_view_name",
        ),
        Index("ix_saved_views_owner", "workspace_id", "user_id", "surface"),
    )

    id: str = Field(primary_key=True, default_factory=generate_saved_view_id)
    tenant_id: str = Field(index=True)
    workspace_id: str = Field(index=True)
    user_id: str = Field(index=True)

    surface: str = Field(index=True, max_length=64)
    """Which screen the view belongs to, e.g. "runs" or "traces"."""

    name: str = Field(max_length=128)
    query: str = Field(max_length=2048)
    """The screen's own query string, without a leading question mark."""

    is_default: bool = Field(default=False)
    """Applied when the screen opens with no query of its own."""

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class PinnedObject(SQLModel, table=True):
    """Something a person put within reach of every screen.

    Only the reference is kept. The name and state are read live, so a pin
    cannot go stale into a label that describes what an object used to be.
    """

    __tablename__ = "pinned_objects"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "user_id",
            "object_type",
            "object_id",
            name="uq_pinned_object",
        ),
        Index("ix_pinned_objects_owner", "workspace_id", "user_id"),
    )

    id: str = Field(primary_key=True, default_factory=generate_pin_id)
    tenant_id: str = Field(index=True)
    workspace_id: str = Field(index=True)
    user_id: str = Field(index=True)

    object_type: str = Field(index=True, max_length=64)
    object_id: str = Field(index=True, max_length=128)
    label: str | None = Field(default=None, nullable=True, max_length=256)
    """A name captured when pinning, shown only until the object is read."""

    created_at: datetime = Field(default_factory=utc_now)


class UserMfa(SQLModel, table=True):
    """One person's second factor.

    The shared secret is sealed before it is stored: a database dump alone must
    not hand someone the ability to mint codes. Recovery codes are kept as
    hashes and struck off as they are used, so a printed sheet is worth exactly
    as many sign-ins as it has unused lines.

    Enrolment starts pending. It only becomes active once a code proves the
    authenticator actually holds the secret -- activating on setup would let
    someone lock themselves out of their own account with a mistyped scan.
    """

    __tablename__ = "user_mfa"
    # One row per user, so the unique constraint is also the lookup index;
    # a composite on (user_id, status) would only duplicate it.
    __table_args__ = (UniqueConstraint("user_id", name="uq_user_mfa_user"),)

    id: str = Field(primary_key=True, default_factory=generate_user_mfa_id)
    user_id: str = Field(index=True)

    secret_sealed: str = Field(max_length=512)
    """The TOTP secret, sealed with a key derived from the app secret."""

    status: str = Field(default="pending", index=True)
    """pending until a code confirms the enrolment, then active."""

    recovery_hashes_json: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    """SHA-256 of each unused recovery code. Removed on use."""

    confirmed_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    last_used_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class AccountDeletionRequest(SQLModel, table=True):
    """A person asking for their account to be closed, and the pause before it is.

    The pause is the point: a closure asked for in anger or by someone who got
    hold of a live session can be undone until it is due. Nothing is deleted
    while a request is pending.

    Closing an account does not erase what it did. Runs, audits and approvals
    carry the user id because they are evidence of who authorised what, and a
    platform that let a departing account rewrite that record would be no use
    as an audit trail. Closure removes access; it does not remove history.
    """

    __tablename__ = "account_deletion_requests"
    __table_args__ = (
        Index("ix_account_deletion_requests_due", "status", "execute_after"),
    )

    id: str = Field(primary_key=True, default_factory=generate_deletion_request_id)
    user_id: str = Field(index=True)
    tenant_id: str = Field(index=True)

    status: str = Field(default="pending", index=True)
    """pending, cancelled or executed."""

    reason: str | None = Field(default=None, nullable=True, max_length=512)

    requested_at: datetime = Field(default_factory=utc_now)
    execute_after: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
    )
    """When the pause ends. Until then the request can be withdrawn."""

    cancelled_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    executed_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class IdentityToken(SQLModel, table=True):
    """A single-use link the instance mailed to someone.

    Password resets and address verification are the same shape: a secret that
    arrives by mail, works once, and expires. One table with a purpose keeps
    the expiry, single-use and hashing rules in one place instead of copied per
    flow, where one copy eventually forgets one of them.

    Only the hash is stored. A database dump must not yield a working reset
    link, and the person who requested it already has the real one.
    """

    __tablename__ = "identity_tokens"
    __table_args__ = (
        Index("ix_identity_tokens_user_purpose", "user_id", "purpose", "status"),
    )

    id: str = Field(primary_key=True, default_factory=generate_identity_token_id)
    user_id: str = Field(index=True)
    purpose: str = Field(index=True, max_length=32)
    """password_reset or email_verification."""

    token_hash: str = Field(unique=True, index=True)
    status: str = Field(default="pending", index=True)
    """pending, used or superseded."""

    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
    )
    used_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    created_at: datetime = Field(default_factory=utc_now)


class WorkspaceInvitation(SQLModel, table=True):
    """An offer of membership, addressed to an email rather than a user id.

    Adding someone by user id only works for people who already have an
    account, which is why the console could not invite anyone. An invitation
    names the address, the role and who offered it, and is redeemed by whoever
    proves control of that address by following the link.
    """

    __tablename__ = "workspace_invitations"
    __table_args__ = (
        Index("ix_workspace_invitations_scope", "workspace_id", "status"),
    )

    id: str = Field(primary_key=True, default_factory=generate_invitation_id)
    tenant_id: str = Field(index=True)
    workspace_id: str = Field(index=True)
    email: str = Field(index=True, max_length=320)
    role: str = Field(max_length=32)

    token_hash: str = Field(unique=True, index=True)
    status: str = Field(default="pending", index=True)
    """pending, accepted, revoked or expired."""

    invited_by: str | None = Field(default=None, nullable=True)
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
    )
    accepted_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    accepted_user_id: str | None = Field(default=None, nullable=True)
    revoked_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
