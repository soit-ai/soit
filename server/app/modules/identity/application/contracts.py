"""Public identity contracts available to other Community modules."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol


class PolicyScopeResource(Protocol):
    id: str
    egress_allowlist: list[str]
    egress_blocklist: list[str]
    updated_at: datetime


class IdentityPolicyScopePort(Protocol):
    """Resolve tenant/workspace policy resources without exposing repositories."""

    async def get_tenant(self, tenant_id: str) -> PolicyScopeResource | None: ...

    async def get_workspace(self, workspace_id: str) -> PolicyScopeResource | None: ...
