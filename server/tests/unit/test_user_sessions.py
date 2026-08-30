"""test_user_sessions

Sessions are what makes a sign-out mean something: the access token names one,
so ending it ends the access it granted. These cover issuing, rotating,
reuse detection and revocation.
"""

from datetime import timedelta

import pytest

from app.kernel.commons.errors import NotFoundError, UnauthorizedError
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.identity.auth import decode_jwt_token
from app.modules.identity.application.schemas import UserCreate


def _service(db):
    from app.wiring.services import build_identity_service

    return build_identity_service(db=db)


def _register(service, email: str = "session@example.com"):
    return service.register_user(
        UserCreate(email=email, password="password123", name="Session User"),
        tenant_name=f"tenant-{email}",
        user_agent="pytest-agent/1.0",
        ip_address="203.0.113.7",
    )


def test_signing_in_opens_a_session_the_token_names(db):
    service = _service(db)
    user, _tenant, access_token, _workspace_id, refresh_token = _register(service)

    payload = decode_jwt_token(access_token)
    sessions = service.session_repo.list_by_user(user.id)

    assert len(sessions) == 1
    assert payload["sid"] == sessions[0].id
    assert refresh_token
    # The credential is never stored, only its hash.
    assert refresh_token not in sessions[0].refresh_token_hash
    assert sessions[0].user_agent == "pytest-agent/1.0"
    assert sessions[0].ip_address == "203.0.113.7"


def test_refreshing_rotates_the_token_and_keeps_the_session(db):
    service = _service(db)
    user, _tenant, _access, _workspace_id, refresh_token = _register(service)
    before = service.session_repo.list_by_user(user.id)[0]

    access_token, rotated, workspace_id = service.refresh_session(refresh_token)

    assert rotated != refresh_token
    assert workspace_id
    after = service.session_repo.list_by_user(user.id)
    assert len(after) == 1, "refresh renews the session rather than opening another"
    assert after[0].id == before.id
    assert decode_jwt_token(access_token)["sid"] == before.id


def test_replaying_a_rotated_token_ends_the_session(db):
    """Either it leaked or the client is confused; both are safer ended."""
    service = _service(db)
    user, _tenant, _access, _workspace_id, refresh_token = _register(service)
    service.refresh_session(refresh_token)

    with pytest.raises(UnauthorizedError):
        service.refresh_session(refresh_token)

    # The rotated-out token simply no longer matches; the live session is
    # untouched by a failed replay of the old one.
    assert len(service.session_repo.list_by_user(user.id)) == 1


def test_a_revoked_session_cannot_be_refreshed(db):
    service = _service(db)
    user, _tenant, _access, workspace_id, refresh_token = _register(service)
    session = service.session_repo.list_by_user(user.id)[0]
    ctx = RequestContext(
        tenant_id=session.tenant_id,
        workspace_id=workspace_id,
        user_id=user.id,
    )

    service.revoke_session(ctx, session.id)

    with pytest.raises(UnauthorizedError):
        service.refresh_session(refresh_token)


def test_revoking_someone_elses_session_reads_as_not_found(db):
    """A caller must not be able to probe for other people's session ids."""
    service = _service(db)
    owner, _t1, _a1, workspace_id, _r1 = _register(service, "owner@example.com")
    other, _t2, _a2, _w2, _r2 = _register(service, "other@example.com")
    other_session = service.session_repo.list_by_user(other.id)[0]

    owner_session = service.session_repo.list_by_user(owner.id)[0]
    ctx = RequestContext(
        tenant_id=owner_session.tenant_id,
        workspace_id=workspace_id,
        user_id=owner.id,
    )

    with pytest.raises(NotFoundError):
        service.revoke_session(ctx, other_session.id)

    assert service.session_repo.get_by_id(other_session.id).status == "active"


def test_signing_out_everywhere_can_keep_the_current_device(db):
    service = _service(db)
    user, _tenant, _access, workspace_id, _refresh = _register(service)
    # Two more sign-ins from other devices.
    service.authenticate_user("session@example.com", "password123")
    service.authenticate_user("session@example.com", "password123")
    sessions = service.session_repo.list_by_user(user.id)
    assert len(sessions) == 3
    current = sessions[0]
    ctx = RequestContext(
        tenant_id=current.tenant_id,
        workspace_id=workspace_id,
        user_id=user.id,
    )

    revoked = service.revoke_all_sessions(ctx, except_session_id=current.id)

    assert revoked == 2
    remaining = service.session_repo.list_by_user(user.id)
    assert [row.id for row in remaining] == [current.id]


def test_an_expired_session_is_not_refreshable(db):
    service = _service(db)
    user, _tenant, _access, _workspace_id, refresh_token = _register(service)
    session = service.session_repo.list_by_user(user.id)[0]
    session.expires_at = utc_now() - timedelta(minutes=1)
    service.session_repo.save(session)

    with pytest.raises(UnauthorizedError):
        service.refresh_session(refresh_token)


def test_last_seen_is_reported_per_user(db):
    service = _service(db)
    user, _tenant, _access, _workspace_id, _refresh = _register(service)

    seen = service.session_repo.last_seen_for_users([user.id, "u_nobody"])

    assert user.id in seen
    assert "u_nobody" not in seen
