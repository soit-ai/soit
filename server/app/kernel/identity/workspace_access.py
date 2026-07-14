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


class WorkspaceAccessResolver(Protocol):
    """Resolve workspace access from the system of record."""

    def resolve(
        self,
        tenant_id: str,
        workspace_id: str,
        user_id: str,
    ) -> WorkspaceAccess | None:
        """Return effective access or None when membership is absent."""
