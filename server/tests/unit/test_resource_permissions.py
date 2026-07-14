"""test_resource_permissions

Unit tests for resource-level permission checks.
"""

import pytest

from app.kernel.commons.errors import ForbiddenError
from app.kernel.contracts.context import RequestContext
from app.kernel.identity.permissions import (
    PermissionCache,
    register_resource_grant_provider,
    require_resource_read_async,
    require_resource_write_async,
    reset_resource_grant_provider,
)


class AllowExecuteGrantProvider:
    def allows_resource_action(self, *, ctx, resource_type, resource_id, action, effective_action) -> bool:
        return (
            ctx.user_id == "shared-user"
            and resource_type == "workflow"
            and resource_id == "wf-shared"
            and effective_action == "write"
        )


class FailingGrantProvider:
    def allows_resource_action(self, *, ctx, resource_type, resource_id, action, effective_action) -> bool:
        raise RuntimeError("repository unavailable")


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


@pytest.mark.asyncio
async def test_knowledge_resource_alias_allows_owner_read():
    """Knowledge public resource type allows the same owner read path."""
    ctx = RequestContext(
        tenant_id="tenant-1",
        workspace_id="workspace-1",
        user_id="user-1",
        workspace_role="Owner",
    )

    await require_resource_read_async(
        ctx,
        resource_type="knowledge",
        resource_id="kb-1",
    )


def test_permission_cache_key_includes_scope_and_roles():
    cache = PermissionCache()
    owner_ctx = RequestContext(
        tenant_id="tenant-1",
        workspace_id="workspace-1",
        user_id="user-1",
        tenant_role="Owner",
        workspace_role="Owner",
    )
    roleless_ctx = RequestContext(
        tenant_id="tenant-1",
        workspace_id="workspace-1",
        user_id="user-1",
    )

    assert cache._cache_key(owner_ctx, "knowledge", "kb-1", "run") != cache._cache_key(
        roleless_ctx,
        "knowledge",
        "kb-1",
        "run",
    )


@pytest.mark.asyncio
async def test_resource_permission_uses_registered_grant_provider():
    reset_resource_grant_provider()
    register_resource_grant_provider(AllowExecuteGrantProvider())
    ctx = RequestContext(
        tenant_id="tenant-1",
        workspace_id="workspace-1",
        user_id="shared-user",
        workspace_role="Viewer",
    )

    await require_resource_write_async(
        ctx,
        resource_type="workflow",
        resource_id="wf-shared",
    )

    reset_resource_grant_provider()


@pytest.mark.asyncio
async def test_resource_permission_provider_failure_denies_grant():
    reset_resource_grant_provider()
    register_resource_grant_provider(FailingGrantProvider())
    ctx = RequestContext(
        tenant_id="tenant-1",
        workspace_id="workspace-1",
        user_id="shared-user",
        workspace_role="Viewer",
    )

    with pytest.raises(ForbiddenError):
        await require_resource_write_async(
            ctx,
            resource_type="workflow",
            resource_id="wf-shared",
        )

    reset_resource_grant_provider()
