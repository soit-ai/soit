"""test_account_closure

Closing an account ends its access and leaves its history alone. That split is
the whole point: a governed platform whose audit trail a departing account can
rewrite is not an audit trail.
"""

from datetime import timedelta

import pytest

from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.identity.rbac import TENANT_ROLE_OWNER
from app.modules.identity.application.schemas import UserCreate
from app.modules.identity.domain.models import ApiKey, TenantMembership, User


def _service(async_db):
    from app.wiring.services import build_identity_service

    return build_identity_service(db=async_db)


async def _register(service, email: str):
    return await service.register_user(
        UserCreate(email=email, password="password123", name="Closing User"),
        tenant_name=f"tenant-{email}",
    )


def _ctx(user_id: str, tenant_id: str, workspace_id: str) -> RequestContext:
    return RequestContext(tenant_id=tenant_id, workspace_id=workspace_id, user_id=user_id)


async def _add_second_owner(async_db, tenant_id: str) -> None:
    other = User(email=f"other-{tenant_id}@example.com", password_hash="x", name="Other")
    async_db.add(other)
    await async_db.commit()
    async_db.add(TenantMembership(tenant_id=tenant_id, user_id=other.id, role=TENANT_ROLE_OWNER))
    await async_db.commit()


@pytest.mark.asyncio
async def test_closing_an_account_ends_access_and_keeps_history(async_db):
    service = _service(async_db)
    user, tenant, _access, workspace_id, _refresh = await _register(service, "closed@example.com")
    await _add_second_owner(async_db, tenant.id)
    ctx = _ctx(user.id, tenant.id, workspace_id)

    async_db.add(
        ApiKey(
            tenant_id=tenant.id,
            workspace_id=workspace_id,
            user_id=user.id,
            name="ci",
            key_prefix="soit-x",
            key_hash="hash-closed",
            scopes_json=["read"],
        )
    )
    await async_db.commit()

    request = await service.request_account_deletion(ctx, "leaving")
    await service.execute_account_deletion(request)

    assert (await service.user_repo.get_by_id(user.id)).is_active is False
    assert await service.session_repo.list_by_user(user.id) == []
    assert all(key.status == "revoked" for key in await service.api_key_repo.list_by_user(user.id))
    # The audit ledger still names the user: it records who authorised what.
    from sqlmodel import select

    from app.kernel.runtime.db.models.audit import AuditEvent

    rows = (await async_db.exec(select(AuditEvent).where(AuditEvent.subject_user_id == user.id))).all()
    assert rows


@pytest.mark.asyncio
async def test_a_withdrawn_request_is_never_due(async_db):
    service = _service(async_db)
    user, tenant, _access, workspace_id, _refresh = await _register(service, "withdrawn@example.com")
    await _add_second_owner(async_db, tenant.id)
    ctx = _ctx(user.id, tenant.id, workspace_id)

    request = await service.request_account_deletion(ctx)
    await service.cancel_account_deletion(ctx)
    # Even once the pause has elapsed.
    request.execute_after = utc_now() - timedelta(days=1)
    await service.deletion_repo.save(request)

    assert await service.execute_due_account_deletions() == 0
    assert (await service.user_repo.get_by_id(user.id)).is_active is True


@pytest.mark.asyncio
async def test_the_sweep_closes_only_what_is_due(async_db):
    service = _service(async_db)
    soon, tenant_a, _a, ws_a, _ra = await _register(service, "due@example.com")
    later, tenant_b, _b, ws_b, _rb = await _register(service, "not-due@example.com")
    await _add_second_owner(async_db, tenant_a.id)
    await _add_second_owner(async_db, tenant_b.id)

    due_request = await service.request_account_deletion(_ctx(soon.id, tenant_a.id, ws_a))
    due_request.execute_after = utc_now() - timedelta(minutes=1)
    await service.deletion_repo.save(due_request)
    await service.request_account_deletion(_ctx(later.id, tenant_b.id, ws_b))

    closed = await service.execute_due_account_deletions()

    assert closed == 1
    assert (await service.user_repo.get_by_id(soon.id)).is_active is False
    assert (await service.user_repo.get_by_id(later.id)).is_active is True
