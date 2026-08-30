"""test_account_closure

Closing an account ends its access and leaves its history alone. That split is
the whole point: a governed platform whose audit trail a departing account can
rewrite is not an audit trail.
"""

from datetime import timedelta

from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.identity.rbac import TENANT_ROLE_OWNER
from app.modules.identity.application.schemas import UserCreate
from app.modules.identity.domain.models import ApiKey, TenantMembership, User


def _service(db):
    from app.wiring.services import build_identity_service

    return build_identity_service(db=db)


def _register(service, email: str):
    return service.register_user(
        UserCreate(email=email, password="password123", name="Closing User"),
        tenant_name=f"tenant-{email}",
    )


def _ctx(user_id: str, tenant_id: str, workspace_id: str) -> RequestContext:
    return RequestContext(tenant_id=tenant_id, workspace_id=workspace_id, user_id=user_id)


def _add_second_owner(db, tenant_id: str) -> None:
    other = User(email=f"other-{tenant_id}@example.com", password_hash="x", name="Other")
    db.add(other)
    db.commit()
    db.add(TenantMembership(tenant_id=tenant_id, user_id=other.id, role=TENANT_ROLE_OWNER))
    db.commit()


def test_closing_an_account_ends_access_and_keeps_history(db):
    service = _service(db)
    user, tenant, _access, workspace_id, _refresh = _register(service, "closed@example.com")
    _add_second_owner(db, tenant.id)
    ctx = _ctx(user.id, tenant.id, workspace_id)

    db.add(
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
    db.commit()

    request = service.request_account_deletion(ctx, "leaving")
    service.execute_account_deletion(request)

    assert service.user_repo.get_by_id(user.id).is_active is False
    assert service.session_repo.list_by_user(user.id) == []
    assert all(key.status == "revoked" for key in service.api_key_repo.list_by_user(user.id))
    # The audit ledger still names the user: it records who authorised what.
    from sqlmodel import select

    from app.kernel.runtime.db.models.audit import AuditEvent

    rows = db.exec(select(AuditEvent).where(AuditEvent.subject_user_id == user.id)).all()
    assert rows


def test_a_withdrawn_request_is_never_due(db):
    service = _service(db)
    user, tenant, _access, workspace_id, _refresh = _register(service, "withdrawn@example.com")
    _add_second_owner(db, tenant.id)
    ctx = _ctx(user.id, tenant.id, workspace_id)

    request = service.request_account_deletion(ctx)
    service.cancel_account_deletion(ctx)
    # Even once the pause has elapsed.
    request.execute_after = utc_now() - timedelta(days=1)
    service.deletion_repo.save(request)

    assert service.execute_due_account_deletions() == 0
    assert service.user_repo.get_by_id(user.id).is_active is True


def test_the_sweep_closes_only_what_is_due(db):
    service = _service(db)
    soon, tenant_a, _a, ws_a, _ra = _register(service, "due@example.com")
    later, tenant_b, _b, ws_b, _rb = _register(service, "not-due@example.com")
    _add_second_owner(db, tenant_a.id)
    _add_second_owner(db, tenant_b.id)

    due_request = service.request_account_deletion(_ctx(soon.id, tenant_a.id, ws_a))
    due_request.execute_after = utc_now() - timedelta(minutes=1)
    service.deletion_repo.save(due_request)
    service.request_account_deletion(_ctx(later.id, tenant_b.id, ws_b))

    closed = service.execute_due_account_deletions()

    assert closed == 1
    assert service.user_repo.get_by_id(soon.id).is_active is False
    assert service.user_repo.get_by_id(later.id).is_active is True
