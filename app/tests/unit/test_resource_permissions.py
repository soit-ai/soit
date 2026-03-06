"""test_resource_permissions

Unit tests for resource-level permission checks.
"""

import pytest

from app.kernel.contracts.context import RequestContext
from app.kernel.commons.errors import ForbiddenError
from app.kernel.identity.permissions import (
    require_resource_read_async,
    require_resource_write_async,
)


@pytest.mark.asyncio
async def test_resource_permission_allows_owner_read():
    """Owners can read resources."""
    ctx = RequestContext(
        tenant_id="tenant-1",
        workspace_id="workspace-1",
        user_id="user-1",
        workspace_role="Owner",
    )

    await require_resource_read_async(
        ctx,
        resource_type="workflow",
        resource_id="wf-1",
    )


@pytest.mark.asyncio
async def test_resource_permission_denies_viewer_write():
    """Viewers cannot write resources."""
    ctx = RequestContext(
        tenant_id="tenant-1",
        workspace_id="workspace-1",
        user_id="user-1",
        workspace_role="Viewer",
    )

    with pytest.raises(ForbiddenError):
        await require_resource_write_async(
            ctx,
            resource_type="workflow",
            resource_id="wf-1",
        )
