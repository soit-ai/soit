"""Guardrail changes are separated from agent development and execution."""

import pytest

from app.kernel.commons.errors import ForbiddenError
from app.kernel.contracts.context import RequestContext
from app.kernel.identity.api_key_scopes import normalize_scopes
from app.kernel.identity.rbac import (
    require_workspace_governance,
    require_workspace_write,
)


def _ctx(role: str, scopes: frozenset[str] | None = None) -> RequestContext:
    return RequestContext(
        tenant_id="t",
        workspace_id="w",
        user_id="u",
        tenant_role=role,
        workspace_role=role,
        scopes=scopes,
    )


def test_developer_can_build_and_run_but_not_change_guardrails():
    dev = _ctx("Dev")

    # The whole point of the split: whoever runs agents must not be able to
    # widen the boundary those agents operate inside.
    require_workspace_write(dev)
    assert dev.can_write()
    assert not dev.can_govern()
    with pytest.raises(ForbiddenError, match="governance"):
        require_workspace_governance(dev)


@pytest.mark.parametrize("role", ["Owner", "Admin"])
def test_owner_and_admin_may_change_guardrails(role: str):
    ctx = _ctx(role)

    require_workspace_governance(ctx)
    assert ctx.can_govern()


@pytest.mark.parametrize("role", ["Viewer", "Dev"])
def test_roles_below_admin_cannot_govern(role: str):
    assert not _ctx(role).can_govern()


def test_an_admin_role_still_needs_the_admin_scope_to_govern():
    write_scoped = _ctx("Admin", normalize_scopes(["write"]))

    # A credential caps the role, so a write-scoped key held by an Admin
    # cannot reach guardrail changes.
    assert write_scoped.can_write()
    assert not write_scoped.can_govern()
    with pytest.raises(ForbiddenError):
        require_workspace_governance(write_scoped)


def test_an_admin_scoped_key_governs_as_its_role_allows():
    admin_scoped = _ctx("Admin", normalize_scopes(["admin"]))

    require_workspace_governance(admin_scoped)
    assert admin_scoped.can_govern()


def test_a_scope_cannot_promote_a_developer_into_governance():
    dev_with_admin_scope = _ctx("Dev", normalize_scopes(["admin"]))

    assert not dev_with_admin_scope.can_govern()
