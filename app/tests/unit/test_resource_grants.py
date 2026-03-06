"""test_resource_grants

Unit tests for resource-level grants.
"""

import pytest

from app.kernel.contracts.context import RequestContext
from app.kernel.identity.permissions import check_resource_permission
from app.modules.identity.domain.models import ResourceGrant
from app.modules.identity.infra.repository import ResourceGrantRepository


@pytest.mark.asyncio
async def test_resource_grant_allows_action(monkeypatch, db):
    """Resource grant allows elevated actions."""
    from app.infra.db import session as session_module

    monkeypatch.setattr(session_module, "get_db_sync", lambda: db)

    ctx = RequestContext(
        tenant_id="tenant-1",
        workspace_id="workspace-1",
        user_id="user-1",
        workspace_role="Viewer",
    )

    repo = ResourceGrantRepository(db, ctx)
    repo.create(
        ResourceGrant(
            resource_type="dataset",
            resource_id="ds-1",
            user_id=ctx.user_id,
            actions=["WRITE"],
        )
    )
    repo.create(
        ResourceGrant(
            resource_type="workflow",
            resource_id="wf-1",
            user_id=ctx.user_id,
            actions=["run"],
        )
    )

    await check_resource_permission(ctx, "dataset", "ds-1", "update")
    await check_resource_permission(ctx, "workflow", "wf-1", "run")
