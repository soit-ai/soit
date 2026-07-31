"""test_resource_permissions

Unit tests for resource-level permission checks.
"""

from fnmatch import fnmatch

import pytest

import app.kernel.identity.permissions as permissions
from app.kernel.commons.errors import ForbiddenError
from app.kernel.contracts.context import RequestContext
from app.kernel.identity.permissions import (
    PermissionCache,
    register_resource_grant_provider,
    require_resource_delete_async,
    require_resource_read_async,
    require_resource_write_async,
    reset_resource_grant_provider,
)


def _owned_resource_ctx(scopes: frozenset[str] | None) -> RequestContext:
    """Viewer context so only ownership can grant write-level actions."""

    return RequestContext(
        tenant_id="tenant-1",
        workspace_id="workspace-1",
        user_id="owner-user",
        workspace_role="Viewer",
        scopes=scopes,
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


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.values[key] = value

    async def scan_iter(self, match: str):
        for key in list(self.values):
            if fnmatch(key, match):
                yield key

    async def delete(self, key: str) -> None:
        self.values.pop(key, None)


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


@pytest.mark.asyncio
async def test_owner_bypass_allows_interactive_session_write():
    """Ownership still grants write to an unrestricted interactive session."""
    await require_resource_write_async(
        _owned_resource_ctx(scopes=None),
        resource_type="workflow",
        resource_id="wf-owned",
        resource_owner_id="owner-user",
    )


@pytest.mark.asyncio
async def test_owner_bypass_allows_write_scoped_key_write():
    """A write-scoped key may write an owned resource."""
    await require_resource_write_async(
        _owned_resource_ctx(scopes=frozenset({"read", "write"})),
        resource_type="workflow",
        resource_id="wf-owned",
        resource_owner_id="owner-user",
    )


@pytest.mark.asyncio
async def test_owner_bypass_denies_read_scoped_key_write():
    """A read-scoped key must not write even resources its owner created."""
    with pytest.raises(ForbiddenError):
        await require_resource_write_async(
            _owned_resource_ctx(scopes=frozenset({"read"})),
            resource_type="workflow",
            resource_id="wf-owned",
            resource_owner_id="owner-user",
        )


@pytest.mark.asyncio
async def test_owner_bypass_denies_write_scoped_key_delete():
    """Delete sits above write in the ladder, so it needs the admin scope."""
    with pytest.raises(ForbiddenError):
        await require_resource_delete_async(
            _owned_resource_ctx(scopes=frozenset({"read", "write"})),
            resource_type="workflow",
            resource_id="wf-owned",
            resource_owner_id="owner-user",
        )
    await require_resource_delete_async(
        _owned_resource_ctx(scopes=frozenset({"read", "write", "admin"})),
        resource_type="workflow",
        resource_id="wf-owned",
        resource_owner_id="owner-user",
    )


@pytest.mark.asyncio
async def test_resource_grant_respects_scope_ceiling():
    """Explicit grants are capped by the credential scope like every source."""
    register_resource_grant_provider(AllowExecuteGrantProvider())
    try:
        granted_ctx = RequestContext(
            tenant_id="tenant-1",
            workspace_id="workspace-1",
            user_id="shared-user",
            workspace_role="Viewer",
            scopes=frozenset({"read"}),
        )
        with pytest.raises(ForbiddenError):
            await require_resource_write_async(
                granted_ctx,
                resource_type="workflow",
                resource_id="wf-shared",
            )
    finally:
        reset_resource_grant_provider()


def test_permission_cache_key_distinguishes_credential_scopes():
    """A scoped key and an interactive session must never share a cache entry."""
    cache = PermissionCache()
    interactive = _owned_resource_ctx(scopes=None)
    read_key = _owned_resource_ctx(scopes=frozenset({"read"}))
    write_key = _owned_resource_ctx(scopes=frozenset({"read", "write"}))

    keys = {
        cache._cache_key(c, "workflow", "wf-1", "write")
        for c in (interactive, read_key, write_key)
    }
    assert len(keys) == 3


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
async def test_permission_cache_invalidation_is_scoped_and_uses_injected_redis():
    redis = FakeRedis()
    reader_cache = PermissionCache(redis_client=redis)
    writer_cache = PermissionCache(redis_client=redis)
    workspace_one = RequestContext(
        tenant_id="tenant-1",
        workspace_id="workspace-1",
        user_id="shared-user",
        workspace_role="Viewer",
    )
    workspace_two = RequestContext(
        tenant_id="tenant-1",
        workspace_id="workspace-2",
        user_id="shared-user",
        workspace_role="Viewer",
    )

    await reader_cache.set_cached_permission(
        workspace_one, "workflow", "wf-shared", "write", True
    )
    await reader_cache.set_cached_permission(
        workspace_two, "workflow", "wf-shared", "write", True
    )
    assert len(redis.values) == 2

    await writer_cache.invalidate_permission(
        ctx=workspace_one,
        user_id="shared-user",
        resource_type="workflow",
        resource_id="wf-shared",
    )

    assert (
        await reader_cache.get_cached_permission(
            workspace_one, "workflow", "wf-shared", "write"
        )
        is None
    )
    assert (
        await reader_cache.get_cached_permission(
            workspace_two, "workflow", "wf-shared", "write"
        )
        is True
    )


@pytest.mark.asyncio
async def test_explicit_resource_grant_allow_is_not_cached(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setattr(permissions, "_permission_cache", PermissionCache(redis))
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

    assert redis.values == {}
    reset_resource_grant_provider()


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
