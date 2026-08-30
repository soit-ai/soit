"""test_identity_service

Unit tests for IdentityService.
"""

from app.kernel.commons.errors import ValidationError
from app.kernel.contracts.context import RequestContext
from app.kernel.identity.rbac import TENANT_ROLE_OWNER, WORKSPACE_ROLE_OWNER
from app.modules.identity.application.schemas import (
    ApiKeyCreate,
    MembershipCreate,
    UserCreate,
    WorkspaceCreate,
    WorkspaceUpdate,
)
from app.wiring.services import build_identity_service


def test_identity_register_and_authenticate(db):
    """Register user and authenticate with password."""
    service = build_identity_service(db=db)
    user_data = UserCreate(
        email="alice@example.com",
        password="password123",
        name="Alice",
    )

    user, tenant, token, workspace_id, refresh_token = service.register_user(user_data, tenant_name="acme")

    assert user.id
    assert tenant is not None
    assert tenant.id
    assert token
    assert workspace_id

    role = service.get_user_tenant_role(tenant.id, user.id)
    assert role == TENANT_ROLE_OWNER

    authed_user, authed_token, authed_workspace_id, authed_refresh = service.authenticate_user(
        user_data.email,
        user_data.password,
    )
    assert authed_user.id == user.id
    assert authed_token
    assert authed_workspace_id


def test_identity_create_workspace_adds_owner_membership(db):
    """Create workspace adds owner membership for creator."""
    service = build_identity_service(db=db)
    user_data = UserCreate(
        email="bob@example.com",
        password="password456",
        name="Bob",
    )
    user, tenant, _token, _workspace_id, _refresh = service.register_user(user_data, tenant_name="acme-2")

    ctx = RequestContext(
        tenant_id=tenant.id,
        workspace_id="seed-workspace",
        user_id=user.id,
        tenant_role=TENANT_ROLE_OWNER,
        workspace_role=WORKSPACE_ROLE_OWNER,
    )

    workspace = service.create_workspace(
        WorkspaceCreate(name="workspace-a", description="demo"),
        ctx,
    )
    assert workspace.id
    assert workspace.tenant_id == tenant.id

    role = service.get_user_workspace_role(workspace.id, user.id, ctx)
    assert role == WORKSPACE_ROLE_OWNER


def test_identity_update_workspace_quota_fields(db):
    """Tenant admins can set, clear, and are required for workspace quotas."""
    service = build_identity_service(db=db)
    user_data = UserCreate(
        email="dora@example.com",
        password="password123",
        name="Dora",
    )
    user, tenant, _token, _workspace_id, _refresh = service.register_user(user_data, tenant_name="acme-quota")

    ctx = RequestContext(
        tenant_id=tenant.id,
        workspace_id="seed-workspace",
        user_id=user.id,
        tenant_role=TENANT_ROLE_OWNER,
        workspace_role=WORKSPACE_ROLE_OWNER,
    )
    workspace = service.create_workspace(
        WorkspaceCreate(name="workspace-quota", description=None),
        ctx,
    )

    updated = service.update_workspace(
        workspace.id,
        ctx,
        WorkspaceUpdate(llm_rate_limit_per_minute=60, llm_daily_quota=1000),
    )
    assert updated.llm_rate_limit_per_minute == 60
    assert updated.llm_daily_quota == 1000
    assert updated.tool_daily_quota is None

    cleared = service.update_workspace(
        workspace.id,
        ctx,
        WorkspaceUpdate(llm_rate_limit_per_minute=None),
    )
    assert cleared.llm_rate_limit_per_minute is None
    assert cleared.llm_daily_quota == 1000

    dev_ctx = RequestContext(
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        user_id=user.id,
        tenant_role="Dev",
        workspace_role="Dev",
    )
    try:
        service.update_workspace(
            workspace.id,
            dev_ctx,
            WorkspaceUpdate(llm_daily_quota=5),
        )
        raise AssertionError("Expected ValidationError for non tenant-admin quota change")
    except ValidationError:
        pass


def test_identity_api_key_lifecycle(db):
    """Create, rotate, and revoke API keys."""
    service = build_identity_service(db=db)
    user_data = UserCreate(
        email="carol@example.com",
        password="password789",
        name="Carol",
    )
    user, tenant, _token, _workspace_id, _refresh = service.register_user(user_data, tenant_name="acme-3")

    seed_ctx = RequestContext(
        tenant_id=tenant.id,
        workspace_id="seed-workspace",
        user_id=user.id,
        tenant_role=TENANT_ROLE_OWNER,
        workspace_role=WORKSPACE_ROLE_OWNER,
    )
    workspace = service.create_workspace(
        WorkspaceCreate(name="workspace-b", description="demo"),
        seed_ctx,
    )

    ctx = RequestContext(
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        user_id=user.id,
        tenant_role=TENANT_ROLE_OWNER,
        workspace_role=WORKSPACE_ROLE_OWNER,
    )

    api_key, raw_key = service.create_api_key(
        ApiKeyCreate(name="primary", scopes=["write"], expires_in_days=30),
        ctx,
    )
    assert raw_key.startswith("sk_")
    assert api_key.key_prefix == raw_key[:12]
    assert api_key.status == "active"
    # "write" implies "read", so the stored grant is explicit rather than
    # requiring every caller to expand the hierarchy.
    assert api_key.scopes_json == ["read", "write"]
    assert api_key.expires_at is not None

    keys = service.list_api_keys(ctx, limit=10, offset=0)
    assert any(item.id == api_key.id for item in keys)

    rotated_key, rotated_raw = service.rotate_api_key(api_key.id, ctx)
    assert rotated_key.id != api_key.id
    assert rotated_key.status == "active"
    assert rotated_raw.startswith("sk_")
    # Rotation replaces the secret, not the grant.
    assert rotated_key.scopes_json == ["read", "write"]
    assert rotated_key.expires_at is not None

    old_key = service.api_key_repo.get_by_id(api_key.id)
    assert old_key is not None
    assert old_key.status == "revoked"

    revoked = service.revoke_api_key(rotated_key.id, ctx)
    assert revoked.status == "revoked"
    assert revoked.revoked_at is not None


def test_identity_rejects_legacy_roles(db):
    """Legacy roles are rejected by membership APIs."""
    service = build_identity_service(db=db)
    owner_data = UserCreate(
        email="owner@example.com",
        password="password123",
        name="Owner",
    )
    owner, tenant, _token, _workspace_id, _refresh = service.register_user(owner_data, tenant_name="acme-legacy")

    user_data = UserCreate(
        email="member@example.com",
        password="password123",
        name="Member",
    )
    member, _tenant, _token, _workspace_id, _refresh = service.register_user(user_data, tenant_name=None)

    ctx = RequestContext(
        tenant_id=tenant.id,
        workspace_id="seed-workspace",
        user_id=owner.id,
        tenant_role=TENANT_ROLE_OWNER,
        workspace_role=WORKSPACE_ROLE_OWNER,
    )

    try:
        service.add_tenant_member(
            tenant.id,
            MembershipCreate(user_id=member.id, role="Member"),
            ctx,
        )
        raise AssertionError("Expected ValidationError for legacy tenant role")
    except ValidationError:
        pass

    service.add_tenant_member(
        tenant.id,
        MembershipCreate(user_id=member.id, role="Dev"),
        ctx,
    )

    workspace = service.create_workspace(
        WorkspaceCreate(name="workspace-legacy", description=None),
        ctx,
    )

    try:
        service.add_workspace_member(
            workspace.id,
            MembershipCreate(user_id=member.id, role="Maintainer"),
            ctx,
        )
        raise AssertionError("Expected ValidationError for legacy workspace role")
    except ValidationError:
        pass
