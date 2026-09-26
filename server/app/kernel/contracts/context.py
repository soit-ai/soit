""" context

RequestContext and identity/scope primitives.
"""

from collections.abc import Mapping
from dataclasses import asdict, dataclass, fields
from typing import Any, ClassVar


@dataclass(frozen=True)
class RequestContext:
    """Request context containing tenant, workspace, and user information.

    This context is resolved from JWT token/session and request headers/path.
    All workspace-scoped operations must include this context.
    """

    tenant_id: str
    """Tenant ID (required)."""

    workspace_id: str
    """Workspace ID (required for workspace-scoped operations)."""

    user_id: str
    """User ID (required)."""

    request_id: str | None = None
    """Request ID for tracing (optional)."""

    trace_id: str | None = None
    """Trace ID for correlation (optional)."""

    tenant_role: str | None = None
    """User's role in tenant (Owner/Admin/Dev/Viewer)."""

    workspace_role: str | None = None
    """User's role in workspace (Owner/Admin/Dev/Viewer)."""

    llm_rate_limit_per_minute: int | None = None
    """Optional LLM rate limit (requests per minute)."""

    tool_rate_limit_per_minute: int | None = None
    """Optional tool rate limit (requests per minute)."""

    llm_daily_quota: int | None = None
    """Optional LLM daily request quota."""

    tool_daily_quota: int | None = None
    """Optional tool daily request quota."""

    scopes: frozenset[str] | None = None
    """Ceiling imposed by a programmatic credential.

    None means no credential restriction (an interactive session). A set
    narrows what the caller's role would otherwise allow; it never widens it.
    """

    api_key_id: str | None = None
    """The API key that authenticated the request, when one did.

    Per-key limits, cost attribution and audit use it; the user it belongs to
    stays ``user_id``.
    """

    api_key_rate_limit_per_minute: int | None = None
    """Model calls the authenticating key may make per minute.

    Applies on top of the member's own rate; a key cannot exceed either.
    """

    api_key_daily_request_quota: int | None = None
    """Model calls the authenticating key may make in any 24 hours."""

    api_key_daily_token_quota: int | None = None
    """Model tokens the authenticating key may consume per UTC day."""

    allowed_models: frozenset[str] | None = None
    """Model refs the credential may call; None allows every model."""

    content_capture: str | None = None
    """What runs record of content: ``full`` or ``metadata_only``.

    Resolved at authentication from the workspace setting and the API key,
    whichever keeps less. None means it was not resolved, and the trace
    writer looks the workspace setting up itself.
    """

    _SET_FIELDS: ClassVar[tuple[str, ...]] = ("scopes", "allowed_models")

    def to_json(self) -> dict[str, Any]:
        """The context as JSON, for records that resume work later.

        Set-valued fields have no JSON form; they are stored as sorted lists
        and come back as sets in :meth:`from_json`.
        """
        data = asdict(self)
        for name in self._SET_FIELDS:
            value = getattr(self, name)
            if value is not None:
                data[name] = sorted(value)
        return data

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> "RequestContext":
        """Rebuild a context stored with :meth:`to_json`.

        Keys this contract does not know are ignored, so a record written by a
        newer release still resumes on an older worker during a rollout.
        """
        known = {field.name for field in fields(cls)}
        values: dict[str, Any] = {key: value for key, value in data.items() if key in known}
        for name in cls._SET_FIELDS:
            items = values.get(name)
            if items is not None:
                values[name] = frozenset(str(item) for item in items)
        return cls(**values)

    def has_scope(self, scope: str) -> bool:
        """Return whether the credential permits this scope."""
        return self.scopes is None or scope in self.scopes

    def is_tenant_admin(self) -> bool:
        """Check if user is tenant admin or owner.

        Returns:
            True if user has tenant admin/owner role.
        """
        # Tenant administration is the widest authority available, so a
        # credential must carry the admin scope to exercise it.
        return self.tenant_role in ("Owner", "Admin") and self.has_scope("admin")

    def is_workspace_admin(self) -> bool:
        """Check if user is workspace admin.

        Returns:
            True if user is workspace admin.
        """
        return self.workspace_role == "Admin" and self.has_scope("admin")

    def is_workspace_owner(self) -> bool:
        """Check if user is workspace owner.

        Returns:
            True if user is workspace owner.
        """
        return self.workspace_role == "Owner" and self.has_scope("admin")

    def is_workspace_dev(self) -> bool:
        """Check if user is workspace dev (write-level) or higher.

        Returns:
            True if user has workspace dev/admin/owner role.
        """
        return self.workspace_role in ("Owner", "Admin", "Dev") and self.has_scope(
            "write"
        )

    def is_workspace_viewer(self) -> bool:
        """Check if user has workspace read access.

        Returns:
            True if user has any workspace role.
        """
        return self.workspace_role in (
            "Owner",
            "Admin",
            "Dev",
            "Viewer",
        ) and self.has_scope("read")

    def can_write(self) -> bool:
        """Check if user can write to workspace.

        Returns:
            True if user can write (Owner/Admin/Dev).
        """
        return self.is_workspace_dev()

    def can_read(self) -> bool:
        """Check if user can read from workspace.

        Returns:
            True if user can read (any role).
        """
        return self.is_workspace_viewer()

    def can_govern(self) -> bool:
        """Check if the caller may change workspace guardrails.

        Egress policy, secrets and plugin installation decide what agents are
        allowed to reach and run with. Separating that authority from Dev means
        whoever builds and runs agents cannot also widen the boundary those
        agents operate inside.
        """
        return self.workspace_role in ("Owner", "Admin") and self.has_scope("admin")
