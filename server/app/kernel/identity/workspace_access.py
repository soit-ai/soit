"""Workspace access contracts used during request authentication."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class WorkspaceAccess:
    """Authoritative workspace membership and effective quota values."""

    tenant_role: str
    workspace_role: str
    llm_rate_limit_per_minute: int | None = None
    tool_rate_limit_per_minute: int | None = None
    llm_daily_quota: int | None = None
    tool_daily_quota: int | None = None
    content_capture: str = "full"
    """What runs in the workspace record of content: full or metadata_only."""
    tenant_id: str | None = None
    """The tenant the workspace belongs to: the one a request through it acts in."""


class WorkspaceAccessResolver(Protocol):
    """Resolve workspace access from the system of record."""

    async def resolve(
        self,
        tenant_id: str | None,
        workspace_id: str,
        user_id: str,
        session_id: str | None = None,
    ) -> WorkspaceAccess | None:
        """Return effective access or None when membership is absent.

        ``tenant_id`` pins the tenant the workspace must belong to. None means
        the workspace's own tenant, whichever that is; the caller then acts in
        ``WorkspaceAccess.tenant_id``. Membership of that tenant and of the
        workspace is required either way.

        ``session_id`` names the sign-in the caller's token belongs to, when it
        has one. An implementation that tracks sessions rejects a token whose
        session has ended.
        """
