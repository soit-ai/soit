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

    async def resolve(self, tenant_id: str, workspace_id: str, user_id: str, session_id=None):
        self.calls.append((tenant_id, workspace_id, user_id))
        return SimpleNamespace(
            tenant_role="Viewer",
            workspace_role="Viewer",
            llm_rate_limit_per_minute=None,
            tool_rate_limit_per_minute=None,
            llm_daily_quota=None,
            tool_daily_quota=None,
            content_capture="full",
        )


async def _resolve_none(tenant_id, workspace_id, user_id, session_id=None):  # noqa: ARG001
    return None


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
            "async_client": ("testclient", 50000),
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
    access_resolver.resolve = _resolve_none
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


@pytest.mark.asyncio
async def test_api_key_scopes_reach_the_request_context(async_db, monkeypatch) -> None:
    raw_key = "soit-test-key-scoped"
    async_db.add(
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
    await async_db.commit()

    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.infra.db import session as session_module

    engine = async_db.bind
    monkeypatch.setattr(
        session_module, "get_async_session_local", lambda: (lambda: AsyncSession(bind=engine, expire_on_commit=False))
    )
    resolver = ContextResolver(
        _JWTManager(),
        workspace_access_resolver=_WorkspaceAccessResolver(),
    )

    context = await resolver.resolve_from_api_key(raw_key, None)

    # The stub resolver reports an Owner workspace role; the scope must still
    # cap the credential to reads.
    assert context.scopes == frozenset({"read"})
    assert context.can_read()
    assert not context.can_write()


@pytest.mark.asyncio
async def test_api_key_past_its_expiry_is_rejected(async_db, monkeypatch) -> None:
    raw_key = "soit-test-key-expired"
    async_db.add(
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
    await async_db.commit()

    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.infra.db import session as session_module

    engine = async_db.bind
    monkeypatch.setattr(
        session_module, "get_async_session_local", lambda: (lambda: AsyncSession(bind=engine, expire_on_commit=False))
    )
    resolver = ContextResolver(
        _JWTManager(),
        workspace_access_resolver=_WorkspaceAccessResolver(),
    )

    with pytest.raises(UnauthorizedError, match="expired"):
        await resolver.resolve_from_api_key(raw_key, None)


@pytest.mark.asyncio
async def test_api_key_without_a_usable_scope_is_refused(async_db, monkeypatch) -> None:
    raw_key = "soit-test-key-unscoped"
    async_db.add(
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
    await async_db.commit()

    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.infra.db import session as session_module

    engine = async_db.bind
    monkeypatch.setattr(
        session_module, "get_async_session_local", lambda: (lambda: AsyncSession(bind=engine, expire_on_commit=False))
    )
    resolver = ContextResolver(
        _JWTManager(),
        workspace_access_resolver=_WorkspaceAccessResolver(),
    )

    # Falling back to the owner's role is exactly the inheritance scopes remove.
    with pytest.raises(ForbiddenError, match="usable scope"):
        await resolver.resolve_from_api_key(raw_key, None)


@pytest.mark.asyncio
async def test_api_key_workspace_header_overrides_bound_workspace(async_db, monkeypatch) -> None:
    raw_key = "soit-test-key-override"
    async_db.add(
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
    await async_db.commit()

    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.infra.db import session as session_module

    engine = async_db.bind
    monkeypatch.setattr(
        session_module, "get_async_session_local", lambda: (lambda: AsyncSession(bind=engine, expire_on_commit=False))
    )
    access_resolver = _WorkspaceAccessResolver()
    resolver = ContextResolver(
        _JWTManager(),
        workspace_access_resolver=access_resolver,
    )

    context = await resolver.resolve_from_api_key(raw_key, "workspace-b")

    assert context.tenant_id == "tenant-1"
    assert context.workspace_id == "workspace-b"
    assert access_resolver.calls == [("tenant-1", "workspace-b", "user-1")]


@pytest.mark.asyncio
async def test_api_key_without_header_keeps_bound_workspace(async_db, monkeypatch) -> None:
    raw_key = "soit-test-key-default"
    async_db.add(
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
    await async_db.commit()

    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.infra.db import session as session_module

    engine = async_db.bind
    monkeypatch.setattr(
        session_module, "get_async_session_local", lambda: (lambda: AsyncSession(bind=engine, expire_on_commit=False))
    )
    access_resolver = _WorkspaceAccessResolver()
    resolver = ContextResolver(
        _JWTManager(),
        workspace_access_resolver=access_resolver,
    )

    context = await resolver.resolve_from_api_key(raw_key)

    assert context.workspace_id == "workspace-a"
    assert access_resolver.calls == [("tenant-1", "workspace-a", "user-1")]


@pytest.mark.asyncio
async def test_api_key_workspace_header_requires_target_membership(async_db, monkeypatch) -> None:
    raw_key = "soit-test-key-forbidden"
    async_db.add(
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
    await async_db.commit()

    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.infra.db import session as session_module

    engine = async_db.bind
    monkeypatch.setattr(
        session_module, "get_async_session_local", lambda: (lambda: AsyncSession(bind=engine, expire_on_commit=False))
    )
    access_resolver = _WorkspaceAccessResolver()
    access_resolver.resolve = _resolve_none
    resolver = ContextResolver(
        _JWTManager(),
        workspace_access_resolver=access_resolver,
    )

    with pytest.raises(ForbiddenError, match="workspace"):
        await resolver.resolve_from_api_key(raw_key, "workspace-b")


@pytest.mark.asyncio
async def test_api_key_requires_current_workspace_membership(async_db, monkeypatch) -> None:
    raw_key = "soit-test-key"
    async_db.add(
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
    await async_db.commit()

    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.infra.db import session as session_module

    engine = async_db.bind
    monkeypatch.setattr(
        session_module, "get_async_session_local", lambda: (lambda: AsyncSession(bind=engine, expire_on_commit=False))
    )
    access_resolver = _WorkspaceAccessResolver()
    access_resolver.resolve = _resolve_none
    resolver = ContextResolver(
        _JWTManager(),
        workspace_access_resolver=access_resolver,
    )

    with pytest.raises(ForbiddenError, match="workspace"):
        await resolver.resolve_from_api_key(raw_key)


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
    # handler answers 403 and keeps the code and details, which is how a async_client
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


@pytest.mark.asyncio
async def test_database_access_resolver_requires_tenant_membership(async_db, monkeypatch) -> None:
    async_db.add(Tenant(id="tenant-1", name="Tenant"))
    async_db.add(Workspace(id="workspace-a", tenant_id="tenant-1", name="Workspace"))
    async_db.add(
        WorkspaceMembership(
            tenant_id="tenant-1",
            workspace_id="workspace-a",
            user_id="user-1",
            role="Owner",
        )
    )
    await async_db.commit()

    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.modules.identity.infra import workspace_access as access_module

    engine = async_db.bind
    monkeypatch.setattr(
        access_module, "get_async_session_local", lambda: (lambda: AsyncSession(bind=engine, expire_on_commit=False))
    )

    assert (
        await DatabaseWorkspaceAccessResolver().resolve(
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

def _bind_sessions(async_db, monkeypatch) -> None:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.infra.db import session as session_module

    engine = async_db.bind
    monkeypatch.setattr(
        session_module,
        "get_async_session_local",
        lambda: (lambda: AsyncSession(bind=engine, expire_on_commit=False)),
    )


async def _issue_key(async_db, raw_key: str, **fields) -> ApiKey:
    key = ApiKey(
        tenant_id="tenant-1",
        workspace_id="workspace-a",
        user_id="user-1",
        name="Gateway key",
        key_prefix=raw_key[:12],
        key_hash=hashlib.sha256(raw_key.encode("utf-8")).hexdigest(),
        scopes_json=["read", "write"],
        **fields,
    )
    async_db.add(key)
    await async_db.commit()
    return key


@pytest.mark.asyncio
async def test_a_bearer_api_key_authenticates_like_the_api_key_header(async_db, monkeypatch) -> None:
    raw_key = "sk_bearer-sent-by-an-openai-sdk"
    key = await _issue_key(async_db, raw_key)
    _bind_sessions(async_db, monkeypatch)
    resolver = ContextResolver(_JWTManager(), workspace_access_resolver=_WorkspaceAccessResolver())

    context = await resolver.resolve_from_request(
        _request(),
        authorization=HTTPAuthorizationCredentials(scheme="Bearer", credentials=raw_key),
    )

    assert context.api_key_id == key.id
    assert context.user_id == "user-1"
    assert context.scopes == frozenset({"read", "write"})


@pytest.mark.asyncio
async def test_last_used_is_written_at_most_once_a_minute(async_db, monkeypatch) -> None:
    raw_key = "sk_frequently-used-key"
    key = await _issue_key(async_db, raw_key)
    _bind_sessions(async_db, monkeypatch)
    resolver = ContextResolver(_JWTManager(), workspace_access_resolver=_WorkspaceAccessResolver())

    await resolver.resolve_from_api_key(raw_key, None)
    await async_db.refresh(key)
    first = key.last_used_at
    assert first is not None

    await resolver.resolve_from_api_key(raw_key, None)
    await async_db.refresh(key)
    assert key.last_used_at == first

    key.last_used_at = utc_now() - timedelta(minutes=5)
    async_db.add(key)
    await async_db.commit()
    await resolver.resolve_from_api_key(raw_key, None)
    await async_db.refresh(key)
    assert key.last_used_at is not None and key.last_used_at > first - timedelta(minutes=5)


@pytest.mark.asyncio
async def test_request_ids_are_added_without_dropping_the_key_or_scope(monkeypatch) -> None:
    resolved = RequestContext(
        tenant_id="tenant-1",
        workspace_id="workspace-a",
        user_id="user-1",
        scopes=frozenset({"read"}),
        api_key_id="key-1",
    )

    class _Resolver:
        async def resolve_from_request(self, request, **_):
            return resolved

    monkeypatch.setattr(auth_middleware, "get_context_resolver", lambda: _Resolver())
    request = _request()
    request.state.request_id = "req-1"

    context = await auth_middleware.get_current_context(
        request, credentials=None, x_workspace_id=None, x_api_key=None
    )

    assert context.request_id == "req-1"
    assert context.scopes == frozenset({"read"})
    assert context.api_key_id == "key-1"

@pytest.mark.asyncio
async def test_a_keys_limits_reach_the_request_context(async_db, monkeypatch) -> None:
    raw_key = "sk_limited-gateway-key"
    await _issue_key(
        async_db,
        raw_key,
        rate_limit_per_minute=5,
        daily_request_quota=100,
        daily_token_quota=50_000,
        allowed_models_json=["model:openai-main:gpt-live"],
    )
    _bind_sessions(async_db, monkeypatch)
    resolver = ContextResolver(_JWTManager(), workspace_access_resolver=_WorkspaceAccessResolver())

    context = await resolver.resolve_from_api_key(raw_key, None)

    assert context.api_key_rate_limit_per_minute == 5
    assert context.api_key_daily_request_quota == 100
    assert context.api_key_daily_token_quota == 50_000
    assert context.allowed_models == frozenset({"model:openai-main:gpt-live"})


@pytest.mark.asyncio
async def test_an_ip_allowlist_admits_only_its_ranges(async_db, monkeypatch) -> None:
    raw_key = "sk_office-only-key"
    await _issue_key(async_db, raw_key, ip_allowlist_json=["203.0.113.0/24"])
    _bind_sessions(async_db, monkeypatch)
    resolver = ContextResolver(_JWTManager(), workspace_access_resolver=_WorkspaceAccessResolver())

    admitted = await resolver.resolve_from_api_key(raw_key, None, client_address="203.0.113.9")
    assert admitted.api_key_id is not None
    for address in ("198.51.100.1", None):
        with pytest.raises(ForbiddenError) as refused:
            await resolver.resolve_from_api_key(raw_key, None, client_address=address)
        assert refused.value.details == {"reason": "ip_not_allowed"}


@pytest.mark.asyncio
async def test_the_allowlist_sees_the_client_behind_a_trusted_proxy(async_db, monkeypatch) -> None:
    from app.settings.settings import settings

    raw_key = "sk_proxied-office-key"
    await _issue_key(async_db, raw_key, ip_allowlist_json=["203.0.113.0/24"])
    _bind_sessions(async_db, monkeypatch)
    monkeypatch.setattr(settings, "trusted_proxies", ["10.0.0.0/8"])
    resolver = ContextResolver(_JWTManager(), workspace_access_resolver=_WorkspaceAccessResolver())

    def proxied(forwarded: str) -> Request:
        return Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/v1/models",
                "headers": [
                    (b"authorization", f"Bearer {raw_key}".encode()),
                    (b"x-forwarded-for", forwarded.encode()),
                ],
                "query_string": b"",
                "client": ("10.0.0.2", 443),
            }
        )

    context = await resolver.resolve_from_request(proxied("198.51.100.1, 203.0.113.9"))
    assert context.api_key_id is not None
    # The client wrote the left entry itself; only the proxy's hop counts.
    with pytest.raises(ForbiddenError):
        await resolver.resolve_from_request(proxied("203.0.113.9, 198.51.100.1"))

@pytest.mark.asyncio
async def test_a_key_can_tighten_but_not_loosen_content_capture(async_db, monkeypatch) -> None:
    await _issue_key(async_db, "sk_private-key", content_capture="metadata_only")
    await _issue_key(async_db, "sk_ordinary-key")
    _bind_sessions(async_db, monkeypatch)

    class _PrivateWorkspace(_WorkspaceAccessResolver):
        async def resolve(self, tenant_id, workspace_id, user_id, session_id=None):
            access = await super().resolve(tenant_id, workspace_id, user_id, session_id)
            access.content_capture = "metadata_only"
            return access

    open_workspace = ContextResolver(_JWTManager(), workspace_access_resolver=_WorkspaceAccessResolver())
    private_workspace = ContextResolver(_JWTManager(), workspace_access_resolver=_PrivateWorkspace())

    assert (await open_workspace.resolve_from_api_key("sk_private-key")).content_capture == "metadata_only"
    assert (await open_workspace.resolve_from_api_key("sk_ordinary-key")).content_capture == "full"
    assert (await private_workspace.resolve_from_api_key("sk_ordinary-key")).content_capture == "metadata_only"
