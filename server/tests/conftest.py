"""tests.conftest

Pytest fixtures shared by test suite.

Important:
- Keep imports light at module import time (pytest always imports conftest).
- Heavy deps (sqlalchemy/TestClient/app) are imported lazily inside fixtures.
"""

from __future__ import annotations

import pytest

from app.kernel.commons.ids import generate_ulid
from app.kernel.contracts.context import RequestContext


@pytest.fixture
def ctx() -> RequestContext:
    """Default request context for tests."""
    return RequestContext(
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        user_id="test-user",
        request_id=generate_ulid(),
        tenant_role="Owner",
        workspace_role="Owner",
    )



@pytest.fixture
def tenant1_ctx() -> RequestContext:
    return RequestContext(
        tenant_id="tenant_1",
        workspace_id="workspace_1",
        user_id="user_1",
        request_id=generate_ulid(),
        tenant_role="Owner",
        workspace_role="Owner",
    )


@pytest.fixture
def tenant2_ctx() -> RequestContext:
    return RequestContext(
        tenant_id="tenant_2",
        workspace_id="workspace_1",
        user_id="user_2",
        request_id=generate_ulid(),
        tenant_role="Owner",
        workspace_role="Owner",
    )


@pytest.fixture
def test_context(ctx: RequestContext) -> RequestContext:
    """Alias used by some fixtures/tests."""
    return ctx


@pytest.fixture
def db():
    """In-memory SQLite DB session for tests.

    Lazily imports sqlalchemy/sqlmodel to avoid hard dependency for pure-unit tests.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool
    from sqlmodel import Session, SQLModel

    import app.kernel.runtime.db.models  # noqa: F401

    # Ensure models are imported so SQLModel.metadata is populated.
    # Importing modules is safe in test env and keeps create_all deterministic.
    import app.modules  # noqa: F401

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
        SQLModel.metadata.drop_all(engine)


@pytest.fixture
def client(db, ctx: RequestContext):
    """FastAPI TestClient with DB dependency override."""
    from fastapi.testclient import TestClient

    from app.infra.db.session import get_db
    from app.main import app
    from app.middleware.auth import get_current_context
    from app.settings.settings import settings

    def _override_get_db():
        try:
            yield db
        finally:
            pass

    async def _override_get_current_context() -> RequestContext:
        return ctx

    previous_knowledge_ingest_worker_enabled = getattr(settings, "knowledge_ingest_worker_enabled", False)
    previous_outbox_dispatcher_enabled = getattr(settings, "outbox_dispatcher_enabled", False)
    settings.knowledge_ingest_worker_enabled = False
    settings.outbox_dispatcher_enabled = False
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_context] = _override_get_current_context
    try:
        with TestClient(app) as c:
            yield c
    finally:
        settings.knowledge_ingest_worker_enabled = previous_knowledge_ingest_worker_enabled
        settings.outbox_dispatcher_enabled = previous_outbox_dispatcher_enabled
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_context, None)


@pytest.fixture(autouse=True)
def _clear_registry(test_context: RequestContext):
    """Ensure runtime registry is isolated per test (tenant/workspace scope)."""
    from app.kernel.identity.permissions import reset_resource_grant_provider
    from app.kernel.registry.deps import get_registry
    from app.kernel.security.egress import reset_egress_scope_policy_provider

    reset_resource_grant_provider()
    reset_egress_scope_policy_provider()
    reg = get_registry()
    reg.clear_scope(tenant_id=test_context.tenant_id, workspace_id=test_context.workspace_id)
    yield
    reg.clear_scope(tenant_id=test_context.tenant_id, workspace_id=test_context.workspace_id)
    reset_resource_grant_provider()
    reset_egress_scope_policy_provider()
