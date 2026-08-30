"""Unit tests for authoritative workspace access resolution."""

import hashlib
from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials

from app.auth.context_resolver import ContextResolver
from app.kernel.commons.errors import ForbiddenError, UnauthorizedError
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.middleware import auth as auth_middleware
from app.modules.identity.domain.models import (
    ApiKey,
    Tenant,
    Workspace,
    WorkspaceMembership,
)
from app.modules.identity.infra.workspace_access import DatabaseWorkspaceAccessResolver


class _JWTManager:
    def decode_token(self, token: str) -> dict[str, str]:
        assert token == "token"
        return {
            "sub": "user-1",
            "tenant_id": "tenant-1",
            "workspace_id": "workspace-a",
            "workspace_role": "Owner",
        }


class _WorkspaceAccessResolver:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    def resolve(self, tenant_id: str, workspace_id: str, user_id: str, session_id=None):
        self.calls.append((tenant_id, workspace_id, user_id))
        return SimpleNamespace(
            tenant_role="Viewer",
            workspace_role="Viewer",
            llm_rate_limit_per_minute=None,
            tool_rate_limit_per_minute=None,
            llm_daily_quota=None,
            tool_daily_quota=None,
        )


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/runs",
            "headers": [],
            "query_string": b"",
            "scheme": "http",
            "server": ("testserver", 80),
            "client": ("testclient", 50000),
        }
    )


@pytest.mark.asyncio
async def test_header_workspace_uses_authoritative_membership_role() -> None:
    access_resolver = _WorkspaceAccessResolver()
    resolver = ContextResolver(
        _JWTManager(),
        workspace_access_resolver=access_resolver,
    )

    context = await resolver.resolve_from_request(
        _request(),
        workspace_id_header="workspace-b",
        authorization=HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="token",
        ),
    )

    assert context.workspace_id == "workspace-b"
    assert context.workspace_role == "Viewer"
    assert access_resolver.calls == [("tenant-1", "workspace-b", "user-1")]


@pytest.mark.asyncio
async def test_missing_workspace_membership_is_forbidden() -> None:
    access_resolver = _WorkspaceAccessResolver()
    access_resolver.resolve = lambda tenant_id, workspace_id, user_id, session_id=None: None
    resolver = ContextResolver(
        _JWTManager(),
        workspace_access_resolver=access_resolver,
    )

    with pytest.raises(ForbiddenError, match="workspace"):
        await resolver.resolve_from_request(
            _request(),
            workspace_id_header="workspace-b",
            authorization=HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials="token",
            ),
        )


def test_default_context_resolver_wires_workspace_access_provider(monkeypatch) -> None:
    monkeypatch.setattr(auth_middleware, "_context_resolver", None)

    resolver = auth_middleware.get_context_resolver()

    assert resolver.workspace_access_resolver is not None


def test_context_resolver_requires_workspace_access_provider() -> None:
    with pytest.raises(TypeError):
        ContextResolver(_JWTManager())


@pytest.mark.asyncio
async def test_non_http_token_resolution_uses_authoritative_membership() -> None:
    access_resolver = _WorkspaceAccessResolver()
    resolver = ContextResolver(
        _JWTManager(),
        workspace_access_resolver=access_resolver,
    )

    context = await resolver.resolve_from_token("token", workspace_id="workspace-b")

    assert context.workspace_id == "workspace-b"
    assert context.tenant_role == "Viewer"
    assert context.workspace_role == "Viewer"
    assert access_resolver.calls == [("tenant-1", "workspace-b", "user-1")]


@pytest.mark.asyncio
async def test_tenant_role_comes_from_authoritative_membership() -> None:
    access_resolver = _WorkspaceAccessResolver()
    resolver = ContextResolver(
        _JWTManager(),
        workspace_access_resolver=access_resolver,
    )

    context = await resolver.resolve_from_request(
        _request(),
        workspace_id_header="workspace-b",
        authorization=HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="token",
        ),
    )

    assert context.tenant_role == "Viewer"


def test_api_key_scopes_reach_the_request_context(db, monkeypatch) -> None:
    raw_key = "soit-test-key-scoped"
    db.add(
        ApiKey(
            tenant_id="tenant-1",
            workspace_id="workspace-a",
            user_id="user-1",
            name="Read only key",
            key_prefix="soit-test",
            key_hash=hashlib.sha256(raw_key.encode("utf-8")).hexdigest(),
            scopes_json=["read"],
        )
    )
    db.commit()

    from app.infra.db import session as session_module

    monkeypatch.setattr(session_module, "get_db_sync", lambda: db)
    resolver = ContextResolver(
        _JWTManager(),
        workspace_access_resolver=_WorkspaceAccessResolver(),
    )

    context = resolver.resolve_from_api_key(raw_key, None)

    # The stub resolver reports an Owner workspace role; the scope must still
    # cap the credential to reads.
    assert context.scopes == frozenset({"read"})
    assert context.can_read()
    assert not context.can_write()


def test_api_key_past_its_expiry_is_rejected(db, monkeypatch) -> None:
    raw_key = "soit-test-key-expired"
    db.add(
        ApiKey(
            tenant_id="tenant-1",
            workspace_id="workspace-a",
            user_id="user-1",
            name="Expired key",
            key_prefix="soit-test",
            key_hash=hashlib.sha256(raw_key.encode("utf-8")).hexdigest(),
            scopes_json=["read"],
            expires_at=utc_now() - timedelta(minutes=1),
        )
    )
    db.commit()

    from app.infra.db import session as session_module

    monkeypatch.setattr(session_module, "get_db_sync", lambda: db)
    resolver = ContextResolver(
        _JWTManager(),
        workspace_access_resolver=_WorkspaceAccessResolver(),
    )

    with pytest.raises(UnauthorizedError, match="expired"):
        resolver.resolve_from_api_key(raw_key, None)


def test_api_key_without_a_usable_scope_is_refused(db, monkeypatch) -> None:
    raw_key = "soit-test-key-unscoped"
    db.add(
        ApiKey(
            tenant_id="tenant-1",
            workspace_id="workspace-a",
            user_id="user-1",
            name="Legacy key",
            key_prefix="soit-test",
            key_hash=hashlib.sha256(raw_key.encode("utf-8")).hexdigest(),
            scopes_json=[],
        )
    )
    db.commit()

    from app.infra.db import session as session_module

    monkeypatch.setattr(session_module, "get_db_sync", lambda: db)
    resolver = ContextResolver(
        _JWTManager(),
        workspace_access_resolver=_WorkspaceAccessResolver(),
    )

    # Falling back to the owner's role is exactly the inheritance scopes remove.
    with pytest.raises(ForbiddenError, match="usable scope"):
        resolver.resolve_from_api_key(raw_key, None)


def test_api_key_workspace_header_overrides_bound_workspace(db, monkeypatch) -> None:
    raw_key = "soit-test-key-override"
    db.add(
        ApiKey(
            tenant_id="tenant-1",
            workspace_id="workspace-a",
            user_id="user-1",
            name="Test key",
            key_prefix="soit-test",
            key_hash=hashlib.sha256(raw_key.encode("utf-8")).hexdigest(),
            scopes_json=["read", "write"],
        )
    )
    db.commit()

    from app.infra.db import session as session_module

    monkeypatch.setattr(session_module, "get_db_sync", lambda: db)
    access_resolver = _WorkspaceAccessResolver()
    resolver = ContextResolver(
        _JWTManager(),
        workspace_access_resolver=access_resolver,
    )

    context = resolver.resolve_from_api_key(raw_key, "workspace-b")

    assert context.tenant_id == "tenant-1"
    assert context.workspace_id == "workspace-b"
    assert access_resolver.calls == [("tenant-1", "workspace-b", "user-1")]


def test_api_key_without_header_keeps_bound_workspace(db, monkeypatch) -> None:
    raw_key = "soit-test-key-default"
    db.add(
        ApiKey(
            tenant_id="tenant-1",
            workspace_id="workspace-a",
            user_id="user-1",
            name="Test key",
            key_prefix="soit-test",
            key_hash=hashlib.sha256(raw_key.encode("utf-8")).hexdigest(),
            scopes_json=["read", "write"],
        )
    )
    db.commit()

    from app.infra.db import session as session_module

    monkeypatch.setattr(session_module, "get_db_sync", lambda: db)
    access_resolver = _WorkspaceAccessResolver()
    resolver = ContextResolver(
        _JWTManager(),
        workspace_access_resolver=access_resolver,
    )

    context = resolver.resolve_from_api_key(raw_key)

    assert context.workspace_id == "workspace-a"
    assert access_resolver.calls == [("tenant-1", "workspace-a", "user-1")]


def test_api_key_workspace_header_requires_target_membership(db, monkeypatch) -> None:
    raw_key = "soit-test-key-forbidden"
    db.add(
        ApiKey(
            tenant_id="tenant-1",
            workspace_id="workspace-a",
            user_id="user-1",
            name="Test key",
            key_prefix="soit-test",
            key_hash=hashlib.sha256(raw_key.encode("utf-8")).hexdigest(),
            scopes_json=["read", "write"],
        )
    )
    db.commit()

    from app.infra.db import session as session_module

    monkeypatch.setattr(session_module, "get_db_sync", lambda: db)
    access_resolver = _WorkspaceAccessResolver()
    access_resolver.resolve = lambda tenant_id, workspace_id, user_id: None
    resolver = ContextResolver(
        _JWTManager(),
        workspace_access_resolver=access_resolver,
    )

    with pytest.raises(ForbiddenError, match="workspace"):
        resolver.resolve_from_api_key(raw_key, "workspace-b")


def test_api_key_requires_current_workspace_membership(db, monkeypatch) -> None:
    raw_key = "soit-test-key"
    db.add(
        ApiKey(
            tenant_id="tenant-1",
            workspace_id="workspace-a",
            user_id="user-1",
            name="Test key",
            key_prefix="soit-test",
            key_hash=hashlib.sha256(raw_key.encode("utf-8")).hexdigest(),
            scopes_json=["read", "write"],
        )
    )
    db.commit()

    from app.infra.db import session as session_module

    monkeypatch.setattr(session_module, "get_db_sync", lambda: db)
    access_resolver = _WorkspaceAccessResolver()
    access_resolver.resolve = lambda tenant_id, workspace_id, user_id: None
    resolver = ContextResolver(
        _JWTManager(),
        workspace_access_resolver=access_resolver,
    )

    with pytest.raises(ForbiddenError, match="workspace"):
        resolver.resolve_from_api_key(raw_key)


@pytest.mark.asyncio
async def test_auth_dependency_returns_403_for_missing_workspace_membership(
    monkeypatch,
) -> None:
    class _ForbiddenResolver:
        async def resolve_from_request(self, *args, **kwargs):
            raise ForbiddenError("User is not a member of the requested workspace")

    monkeypatch.setattr(
        auth_middleware,
        "get_context_resolver",
        lambda: _ForbiddenResolver(),
    )

    # Re-raised as the kernel error, not flattened: the app's KernelError
    # handler answers 403 and keeps the code and details, which is how a client
    # tells "enrol a second factor" apart from "you are not a member".
    with pytest.raises(ForbiddenError) as error:
        await auth_middleware.get_current_context(_request())

    assert error.value.code == "FORBIDDEN"


@pytest.mark.asyncio
async def test_auth_dependency_fails_closed_when_access_store_errors(monkeypatch) -> None:
    class _UnavailableResolver:
        async def resolve_from_request(self, *args, **kwargs):
            raise RuntimeError("database credentials leaked here")

    monkeypatch.setattr(
        auth_middleware,
        "get_context_resolver",
        lambda: _UnavailableResolver(),
    )

    with pytest.raises(HTTPException) as error:
        await auth_middleware.get_current_context(_request())

    assert error.value.status_code == 503
    assert error.value.detail == "Authentication service unavailable"


def test_database_access_resolver_requires_tenant_membership(db, monkeypatch) -> None:
    db.add(Tenant(id="tenant-1", name="Tenant"))
    db.add(Workspace(id="workspace-a", tenant_id="tenant-1", name="Workspace"))
    db.add(
        WorkspaceMembership(
            tenant_id="tenant-1",
            workspace_id="workspace-a",
            user_id="user-1",
            role="Owner",
        )
    )
    db.commit()

    from app.modules.identity.infra import workspace_access as access_module

    monkeypatch.setattr(access_module, "get_db_sync", lambda: db)

    assert (
        DatabaseWorkspaceAccessResolver().resolve(
            "tenant-1",
            "workspace-a",
            "user-1",
        )
        is None
    )


@pytest.mark.asyncio
async def test_request_scoped_context_rebuild_preserves_every_field(monkeypatch) -> None:
    """Attaching request ids must not drop any authorization state.

    The dependency rebuilds RequestContext to attach request_id/trace_id.
    Rebuilding by listing fields means a new field is silently lost until
    something notices; scopes were lost exactly that way, which disabled every
    API key ceiling on the real API path.
    """
    from dataclasses import fields

    from app.middleware import auth as auth_middleware

    resolved = RequestContext(
        tenant_id="tenant-1",
        workspace_id="workspace-a",
        user_id="user-1",
        tenant_role="Owner",
        workspace_role="Owner",
        scopes=frozenset({"read"}),
        llm_rate_limit_per_minute=11,
        tool_rate_limit_per_minute=22,
        llm_daily_quota=33,
        tool_daily_quota=44,
    )

    class _Resolver:
        async def resolve_from_request(self, *args, **kwargs):
            return resolved

    monkeypatch.setattr(auth_middleware, "get_context_resolver", lambda: _Resolver())

    request = _request()
    request.state.request_id = "req-1"
    request.state.trace_id = "trace-1"

    context = await auth_middleware.get_current_context(
        request,
        credentials=None,
        x_workspace_id="workspace-a",
        x_api_key="soit-key",
    )

    assert context.request_id == "req-1"
    assert context.trace_id == "trace-1"
    carried = {"request_id", "trace_id"}
    for field in fields(RequestContext):
        if field.name in carried:
            continue
        assert getattr(context, field.name) == getattr(resolved, field.name), (
            f"rebuild dropped {field.name}"
        )
