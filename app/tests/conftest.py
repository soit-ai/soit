""" conftest

Pytest fixtures for scope, db, and gateway mocks.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.infra.db.session import get_db
from app.kernel.contracts.context import RequestContext
from app.kernel.commons.ids import generate_ulid


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db():
    """Create a test database session."""
    from app.infra.db.session import Base
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db):
    """Create a test client."""
    def override_get_db():
        try:
            yield db
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture
def test_context():
    """Create a test request context."""
    return RequestContext(
        tenant_id=generate_ulid(),
        workspace_id=generate_ulid(),
        user_id=generate_ulid(),
    )


@pytest.fixture
def mock_storage_port():
    """Mock storage gateway."""
    from unittest.mock import AsyncMock, MagicMock
    
    gateway = AsyncMock()
    gateway.get = AsyncMock(return_value=b"test content")
    gateway.put = AsyncMock(return_value=None)
    gateway.delete = AsyncMock(return_value=None)
    return gateway


@pytest.fixture
def mock_vector_port():
    """Mock vector gateway."""
    from unittest.mock import AsyncMock, MagicMock
    
    gateway = AsyncMock()
    gateway.insert = AsyncMock(return_value=None)
    gateway.search = AsyncMock(return_value=[])
    gateway.delete = AsyncMock(return_value=None)
    return gateway


@pytest.fixture
def mock_llm_port():
    """Mock LLM gateway."""
    from unittest.mock import AsyncMock, MagicMock
    
    gateway = AsyncMock()
    gateway.complete = AsyncMock(return_value={"text": "test response"})
    gateway.embed = AsyncMock(return_value=[0.1] * 1536)  # Mock embedding vector
    return gateway
