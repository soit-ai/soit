"""Private resource visibility in the kernel permission check."""

from __future__ import annotations

import pytest

from app.kernel.commons.errors import ForbiddenError
from app.kernel.contracts.context import RequestContext
from app.kernel.identity.permissions import (
    RESOURCE_KNOWLEDGE,
    PermissionCache,
    ResourceVisibility,
    check_resource_permission,
    private_resource_hidden,
    register_resource_grant_provider,
    reset_resource_grant_provider,
)

PRIVATE_TO_ALICE = ResourceVisibility(visibility="private", created_by="alice")
SHARED = ResourceVisibility(visibility="workspace", created_by="alice")


def _ctx(user_id: str, role: str, scopes: frozenset[str] | None = None) -> RequestContext:
    return RequestContext(
        tenant_id="tenant-vis",
        workspace_id="workspace-vis",
        user_id=user_id,
        tenant_role="Member",
        workspace_role=role,
        scopes=scopes,
    )


class _GrantFor:
    def __init__(self, user_id: str, actions: set[str]) -> None:
        self.user_id = user_id
        self.actions = actions

    async def allows_resource_action(
        self,
        *,
        ctx: RequestContext,
        resource_type: str,
        resource_id: str,
        action: str,
        effective_action: str,
    ) -> bool:
        del resource_type, resource_id
        return ctx.user_id == self.user_id and (
            action in self.actions or effective_action in self.actions
        )


@pytest.fixture(autouse=True)
def _no_grants():
    reset_resource_grant_provider()
    yield
    reset_resource_grant_provider()


@pytest.mark.parametrize("role", ["Dev", "Viewer"])
@pytest.mark.asyncio
async def test_a_member_who_did_not_create_a_private_resource_cannot_read_it(role: str) -> None:
    with pytest.raises(ForbiddenError):
        await check_resource_permission(
            _ctx("bob", role), RESOURCE_KNOWLEDGE, "kn_1", "read", visibility=PRIVATE_TO_ALICE
        )


@pytest.mark.asyncio
async def test_the_creator_keeps_their_role_rights_on_a_private_resource() -> None:
    await check_resource_permission(
        _ctx("alice", "Dev"), RESOURCE_KNOWLEDGE, "kn_1", "update", visibility=PRIVATE_TO_ALICE
    )
    # Visibility does not widen the ladder: a Dev creator still cannot delete.
    with pytest.raises(ForbiddenError):
        await check_resource_permission(
            _ctx("alice", "Dev"), RESOURCE_KNOWLEDGE, "kn_1", "delete", visibility=PRIVATE_TO_ALICE
        )


@pytest.mark.parametrize("role", ["Owner", "Admin"])
@pytest.mark.asyncio
async def test_owners_and_admins_see_private_resources(role: str) -> None:
    await check_resource_permission(
        _ctx("carol", role), RESOURCE_KNOWLEDGE, "kn_1", "delete", visibility=PRIVATE_TO_ALICE
    )


@pytest.mark.asyncio
async def test_an_owner_with_a_read_scoped_key_reads_but_cannot_write_private() -> None:
    reader = _ctx("carol", "Owner", scopes=frozenset({"read"}))

    await check_resource_permission(
        reader, RESOURCE_KNOWLEDGE, "kn_1", "read", visibility=PRIVATE_TO_ALICE
    )
    with pytest.raises(ForbiddenError):
        await check_resource_permission(
            reader, RESOURCE_KNOWLEDGE, "kn_1", "update", visibility=PRIVATE_TO_ALICE
        )


@pytest.mark.asyncio
async def test_an_explicit_grant_opens_a_private_resource_for_its_actions() -> None:
    register_resource_grant_provider(_GrantFor("bob", {"read"}))

    await check_resource_permission(
        _ctx("bob", "Viewer"), RESOURCE_KNOWLEDGE, "kn_1", "read", visibility=PRIVATE_TO_ALICE
    )
    with pytest.raises(ForbiddenError):
        await check_resource_permission(
            _ctx("bob", "Viewer"),
            RESOURCE_KNOWLEDGE,
            "kn_1",
            "update",
            visibility=PRIVATE_TO_ALICE,
        )


@pytest.mark.asyncio
async def test_workspace_visibility_follows_the_role_ladder() -> None:
    await check_resource_permission(
        _ctx("bob", "Dev"), RESOURCE_KNOWLEDGE, "kn_1", "run", visibility=SHARED
    )
    await check_resource_permission(_ctx("bob", "Viewer"), RESOURCE_KNOWLEDGE, "kn_1", "read")


def test_private_resource_hidden_helper() -> None:
    assert private_resource_hidden(_ctx("bob", "Dev"), PRIVATE_TO_ALICE)
    assert not private_resource_hidden(_ctx("alice", "Dev"), PRIVATE_TO_ALICE)
    assert not private_resource_hidden(_ctx("bob", "Admin"), PRIVATE_TO_ALICE)
    assert not private_resource_hidden(_ctx("bob", "Dev"), SHARED)
    assert not private_resource_hidden(_ctx("bob", "Dev"), None)
    # A private resource without a recorded creator is hidden from non-admins.
    assert private_resource_hidden(
        _ctx("bob", "Dev"), ResourceVisibility(visibility="private", created_by=None)
    )


def test_the_cache_key_changes_with_visibility() -> None:
    cache = PermissionCache()
    ctx = _ctx("bob", "Dev")

    shared_key = cache._cache_key(ctx, RESOURCE_KNOWLEDGE, "kn_1", "read", SHARED)
    private_key = cache._cache_key(ctx, RESOURCE_KNOWLEDGE, "kn_1", "read", PRIVATE_TO_ALICE)
    unknown_key = cache._cache_key(ctx, RESOURCE_KNOWLEDGE, "kn_1", "read", None)

    assert len({shared_key, private_key, unknown_key}) == 3
