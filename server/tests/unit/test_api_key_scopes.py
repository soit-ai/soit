"""API key scopes cap what a credential may do, regardless of the owner's role."""

import pytest

from app.kernel.contracts.context import RequestContext
from app.kernel.identity.api_key_scopes import normalize_scopes, unknown_scopes
from app.modules.identity.application.schemas import ApiKeyCreate

OWNER_ROLES = {"tenant_role": "Owner", "workspace_role": "Owner"}


def _ctx(scopes: frozenset[str] | None) -> RequestContext:
    return RequestContext(
        tenant_id="t",
        workspace_id="w",
        user_id="u",
        scopes=scopes,
        **OWNER_ROLES,
    )


def test_broader_scopes_imply_the_narrower_ones():
    assert normalize_scopes(["write"]) == frozenset({"read", "write"})
    assert normalize_scopes(["admin"]) == frozenset({"read", "write", "admin"})
    assert normalize_scopes(["read"]) == frozenset({"read"})


def test_unknown_scopes_are_dropped_rather_than_trusted():
    # Silently honouring an unrecognised scope would be an escalation path.
    assert normalize_scopes(["read", "superuser"]) == frozenset({"read"})
    assert unknown_scopes(["read", "superuser"]) == ["superuser"]


def test_a_session_without_a_credential_keeps_its_full_role():
    ctx = _ctx(None)

    assert ctx.can_read()
    assert ctx.can_write()
    assert ctx.is_workspace_owner()
    assert ctx.is_tenant_admin()


def test_a_read_scoped_key_cannot_write_even_for_an_owner():
    ctx = _ctx(normalize_scopes(["read"]))

    assert ctx.can_read()
    assert not ctx.can_write()
    assert not ctx.is_workspace_owner()
    assert not ctx.is_tenant_admin()


def test_a_write_scoped_key_cannot_perform_owner_operations():
    ctx = _ctx(normalize_scopes(["write"]))

    assert ctx.can_read()
    assert ctx.can_write()
    assert not ctx.is_workspace_owner()
    assert not ctx.is_tenant_admin()


def test_an_admin_scoped_key_matches_its_owner_role():
    ctx = _ctx(normalize_scopes(["admin"]))

    assert ctx.can_read()
    assert ctx.can_write()
    assert ctx.is_workspace_owner()
    assert ctx.is_tenant_admin()


def test_a_scope_never_grants_more_than_the_role_allows():
    viewer = RequestContext(
        tenant_id="t",
        workspace_id="w",
        user_id="u",
        tenant_role="Viewer",
        workspace_role="Viewer",
        scopes=normalize_scopes(["admin"]),
    )

    # The scope is a ceiling, not a grant: a Viewer stays a Viewer.
    assert viewer.can_read()
    assert not viewer.can_write()
    assert not viewer.is_workspace_owner()


def test_creating_a_key_requires_a_scope_and_a_lifetime():
    with pytest.raises(ValueError):
        ApiKeyCreate(name="k", scopes=[], expires_in_days=30)
    with pytest.raises(ValueError):
        ApiKeyCreate(name="k", scopes=["read"], expires_in_days=0)
    with pytest.raises(ValueError):
        ApiKeyCreate(name="k", scopes=["read"], expires_in_days=400)


def test_creating_a_key_rejects_an_unknown_scope():
    with pytest.raises(ValueError, match="Unknown API key scopes"):
        ApiKeyCreate(name="k", scopes=["superuser"], expires_in_days=30)
