"""Transaction-boundary tests for response persistence repositories."""

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.runtime.db.models.responses import Response, ResponseEvent
from app.kernel.runtime.responses.repository import (
    ResponseEventRepository,
    ResponseRepository,
)

pytestmark = pytest.mark.asyncio


async def test_response_and_events_rollback_as_one_unit(async_db, tenant1_ctx) -> None:
    response_repo = ResponseRepository(async_db, tenant1_ctx)
    event_repo = ResponseEventRepository(async_db, tenant1_ctx)
    response = await response_repo.create(Response(status="queued"))
    event = await event_repo.create(
        ResponseEvent(
            response_id=response.id,
            sequence=1,
            type="response.created",
        )
    )

    await async_db.rollback()

    check = AsyncSession(async_db.bind, expire_on_commit=False)
    try:
        assert await check.get(Response, response.id) is None
        assert await check.get(ResponseEvent, event.id) is None
    finally:
        await check.close()


async def test_response_update_can_be_rolled_back(async_db, tenant1_ctx) -> None:
    response_repo = ResponseRepository(async_db, tenant1_ctx)
    response = await response_repo.create(Response(status="queued"))
    await async_db.commit()

    response.status = "completed"
    await response_repo.update(response)
    await async_db.rollback()

    # Rollback expires every loaded instance; on an async session the reload
    # must be explicit, since attribute access cannot do implicit IO.
    await async_db.refresh(response)
    assert (await response_repo.require(response.id)).status == "queued"
