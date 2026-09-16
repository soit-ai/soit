"""Phase 0 of the async database migration: the async stack works end to end.

Covers the pieces every later phase builds on: the URL/driver mapping, the
async unit of work, the scope-enforcing `AsyncRepository`, and an HTTP round
trip through `async_client`.
"""

import pytest
from sqlmodel import select

from app.infra.db.repository import AsyncRepository
from app.infra.db.session import _async_database_url
from app.infra.db.transaction import AsyncSQLAlchemyUnitOfWork
from app.kernel.commons.ids import generate_ulid
from app.kernel.runtime.db.models.events import EventOutbox


def _outbox_row() -> EventOutbox:
    return EventOutbox(
        event_id=generate_ulid(),
        event_type="test.async_foundation",
        idempotency_key=generate_ulid(),
    )


def test_async_database_url_maps_each_driver():
    assert (
        _async_database_url("postgresql://u:p@h:5432/d")
        == "postgresql+psycopg://u:p@h:5432/d"
    )
    assert _async_database_url("sqlite://") == "sqlite+aiosqlite://"
    assert _async_database_url("sqlite+aiosqlite://") == "sqlite+aiosqlite://"
    assert (
        _async_database_url("postgresql+psycopg://u:p@h/d")
        == "postgresql+psycopg://u:p@h/d"
    )


@pytest.mark.asyncio
async def test_async_repository_enforces_scope(async_db, ctx, tenant2_ctx):
    repo = AsyncRepository(EventOutbox, async_db, ctx)
    other = AsyncRepository(EventOutbox, async_db, tenant2_ctx)

    row = await repo.create(_outbox_row())
    assert row.tenant_id == ctx.tenant_id
    assert row.workspace_id == ctx.workspace_id

    assert (await repo.get_by_id(row.id)) is not None
    assert (await other.get_by_id(row.id)) is None
    assert await repo.count() == 1
    assert await other.count() == 0

    page = await repo.list(page_size=10)
    assert [item.id for item in page.items] == [row.id]

    row.event_type = "test.async_foundation.updated"
    updated = await repo.update(row)
    assert updated.event_type == "test.async_foundation.updated"

    assert await other.delete(row.id) is False
    assert await repo.delete(row.id) is True
    assert await repo.count() == 0


@pytest.mark.asyncio
async def test_async_unit_of_work_commits_on_success_and_rolls_back_on_error(async_db):
    async with AsyncSQLAlchemyUnitOfWork(async_db):
        async_db.add(_outbox_row())

    committed = (await async_db.exec(select(EventOutbox))).all()
    assert len(committed) == 1

    with pytest.raises(RuntimeError, match="abort"):
        async with AsyncSQLAlchemyUnitOfWork(async_db):
            async_db.add(_outbox_row())
            raise RuntimeError("abort")

    after_rollback = (await async_db.exec(select(EventOutbox))).all()
    assert len(after_rollback) == 1


@pytest.mark.asyncio
async def test_async_client_round_trips_through_the_app(async_client):
    response = await async_client.get("/health/live")

    assert response.status_code == 200
    assert response.json()["success"] is True
