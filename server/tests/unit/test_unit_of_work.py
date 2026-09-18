"""Tests for the database unit-of-work boundary."""

import pytest
from starlette.requests import HTTPConnection

from app.infra.db import session as session_module
from app.infra.db import transaction as transaction_module
from app.modules.identity.domain.models import Tenant


def test_transaction_module_exposes_async_unit_of_work() -> None:
    assert hasattr(transaction_module, "AsyncSQLAlchemyUnitOfWork")


@pytest.mark.asyncio
async def test_unit_of_work_commits_successful_transaction(async_db) -> None:
    tenant = Tenant(id="tenant-uow", name="Unit of Work")

    async with transaction_module.AsyncSQLAlchemyUnitOfWork(async_db):
        async_db.add(tenant)

    await async_db.refresh(tenant)
    assert tenant.name == "Unit of Work"


@pytest.mark.asyncio
async def test_unit_of_work_rolls_back_failed_transaction(async_db) -> None:
    tenant = Tenant(id="tenant-uow-rollback", name="Rollback")

    with pytest.raises(RuntimeError, match="abort"):
        async with transaction_module.AsyncSQLAlchemyUnitOfWork(async_db):
            async_db.add(tenant)
            await async_db.flush()
            raise RuntimeError("abort")

    assert await async_db.get(Tenant, tenant.id) is None


class _Session:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0
        self.closes = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1

    async def close(self) -> None:
        self.closes += 1


def _connection() -> HTTPConnection:
    """A bare request scope; `state` is where the session dependency parks the session."""
    return HTTPConnection({"type": "http", "state": {}})


@pytest.mark.asyncio
async def test_request_session_commits_at_dependency_boundary(monkeypatch) -> None:
    db = _Session()
    monkeypatch.setattr(session_module, "get_async_session_local", lambda: lambda: db)
    dependency = session_module.get_async_db(_connection())

    assert await dependency.__anext__() is db
    with pytest.raises(StopAsyncIteration):
        await dependency.__anext__()

    assert db.commits == 1
    assert db.rollbacks == 0
    assert db.closes == 1


@pytest.mark.asyncio
async def test_request_session_rolls_back_dependency_failure(monkeypatch) -> None:
    db = _Session()
    monkeypatch.setattr(session_module, "get_async_session_local", lambda: lambda: db)
    dependency = session_module.get_async_db(_connection())

    await dependency.__anext__()
    with pytest.raises(RuntimeError, match="boom"):
        await dependency.athrow(RuntimeError("boom"))

    assert db.commits == 0
    assert db.rollbacks == 1
    assert db.closes == 1


@pytest.mark.asyncio
async def test_handler_return_commits_the_parked_request_session(monkeypatch) -> None:
    db = _Session()
    monkeypatch.setattr(session_module, "get_async_session_local", lambda: lambda: db)
    connection = _connection()
    session_dependency = session_module.get_async_db(connection)
    await session_dependency.__anext__()

    commit_dependency = session_module.commit_unit_of_work(connection)
    await commit_dependency.__anext__()
    with pytest.raises(StopAsyncIteration):
        await commit_dependency.__anext__()

    # Committed at the handler boundary, while the request session is still open.
    assert db.commits == 1
    assert db.closes == 0
    with pytest.raises(StopAsyncIteration):
        await session_dependency.__anext__()
    assert db.closes == 1


@pytest.mark.asyncio
async def test_handler_failure_skips_the_commit(monkeypatch) -> None:
    db = _Session()
    monkeypatch.setattr(session_module, "get_async_session_local", lambda: lambda: db)
    connection = _connection()
    await session_module.get_async_db(connection).__anext__()

    commit_dependency = session_module.commit_unit_of_work(connection)
    await commit_dependency.__anext__()
    with pytest.raises(RuntimeError, match="boom"):
        await commit_dependency.athrow(RuntimeError("boom"))

    assert db.commits == 0


@pytest.mark.asyncio
async def test_handler_return_without_a_request_session_commits_nothing() -> None:
    commit_dependency = session_module.commit_unit_of_work(_connection())
    await commit_dependency.__anext__()
    with pytest.raises(StopAsyncIteration):
        await commit_dependency.__anext__()
