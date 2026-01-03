"""tests.conftest

Pytest fixtures shared by test suite.

Important:
- Keep imports light at module import time (pytest always imports conftest).
- Heavy deps (sqlalchemy/TestClient/app) are imported lazily inside fixtures.
"""

from __future__ import annotations

import pytest

from app.kernel.contracts.context import RequestContext
from app.kernel.commons.ids import generate_ulid


@pytest.fixture
def ctx() -> RequestContext:
    """Default request context for tests."""
    return RequestContext(
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        user_id="test-user",
        request_id=generate_ulid(),
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
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from sqlmodel import SQLModel

    # Ensure models are imported so SQLModel.metadata is populated.
    # Importing modules is safe in test env and keeps create_all deterministic.
    import app.modules  # noqa: F401

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        SQLModel.metadata.drop_all(engine)


@pytest.fixture
def client(db):
    """FastAPI TestClient with DB dependency override."""
    from fastapi.testclient import TestClient

    from app.main import app
    from app.infra.db.session import get_db

    def _override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture(autouse=True)
def _clear_registry(test_context: RequestContext):
    """Ensure runtime registry is isolated per test (tenant/workspace scope)."""
    from app.kernel.registry.deps import get_registry

    reg = get_registry()
    reg.clear_scope(tenant_id=test_context.tenant_id, workspace_id=test_context.workspace_id)
    yield
    reg.clear_scope(tenant_id=test_context.tenant_id, workspace_id=test_context.workspace_id)
