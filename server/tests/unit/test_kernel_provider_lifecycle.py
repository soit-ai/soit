"""Provider lifecycle tests for kernel extension points."""

from __future__ import annotations

import pytest

from app.kernel.commons.errors import ForbiddenError
from app.kernel.contracts.context import RequestContext
from app.kernel.identity.permissions import (
    get_resource_grant_provider,
    register_resource_grant_provider,
    require_resource_update_async,
    reset_resource_grant_provider,
)
from app.kernel.security.egress import (
    get_egress_scope_policy_provider,
    register_egress_scope_policy_provider,
    reset_egress_scope_policy_provider,
)
from app.wiring.container import get_container, reset_container


class AllowingGrantProvider:
    def allows_resource_action(self, **kwargs) -> bool:
        return True


class EmptyEgressProvider:
    def get_scope_policy(self, ctx: RequestContext):
        return None


def test_provider_reset_restores_kernel_fallback(ctx: RequestContext) -> None:
    _ = ctx
    register_resource_grant_provider(AllowingGrantProvider())
    register_egress_scope_policy_provider(EmptyEgressProvider())

    assert get_resource_grant_provider() is not None
    assert get_egress_scope_policy_provider() is not None

    reset_resource_grant_provider()
    reset_egress_scope_policy_provider()

    assert get_resource_grant_provider() is None
    assert get_egress_scope_policy_provider() is None


def test_container_initialization_registers_kernel_providers() -> None:
    reset_resource_grant_provider()
    reset_egress_scope_policy_provider()
    reset_container()

    get_container()

    assert get_resource_grant_provider() is not None
    assert get_egress_scope_policy_provider() is not None


def test_reset_container_re_registers_kernel_providers() -> None:
    reset_resource_grant_provider()
    reset_egress_scope_policy_provider()

    reset_container()
    get_container()
    first_resource_provider = get_resource_grant_provider()
    first_egress_provider = get_egress_scope_policy_provider()

    reset_container()
    get_container()

    assert get_resource_grant_provider() is not None
    assert get_egress_scope_policy_provider() is not None
    assert get_resource_grant_provider() is not first_resource_provider
    assert get_egress_scope_policy_provider() is not first_egress_provider


@pytest.mark.asyncio
async def test_provider_state_does_not_leak_between_tests(ctx: RequestContext) -> None:
    reset_resource_grant_provider()
    viewer_ctx = RequestContext(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        user_id=ctx.user_id,
        tenant_role="Member",
        workspace_role="Viewer",
    )

    with pytest.raises(ForbiddenError):
        await require_resource_update_async(viewer_ctx, "knowledge", "kn_1", resource_owner_id="other-user")
