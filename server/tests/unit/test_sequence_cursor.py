"""A sequence is read from the database once per transaction, then counted."""

import pytest
from sqlalchemy import text

from app.kernel.runtime.common.sequence_cursor import allocate_sequence


class _Reader:
    def __init__(self, start: int) -> None:
        self.start = start
        self.calls = 0

    async def __call__(self) -> int:
        self.calls += 1
        return self.start


@pytest.mark.asyncio
async def test_later_allocations_in_a_transaction_do_not_touch_the_database(async_db):
    reader = _Reader(start=4)

    first = await allocate_sequence(async_db, "response", "resp_1", reader)
    second = await allocate_sequence(async_db, "response", "resp_1", reader)
    third = await allocate_sequence(async_db, "response", "resp_1", reader)

    assert (first, second, third) == (4, 5, 6)
    assert reader.calls == 1


@pytest.mark.asyncio
async def test_parents_and_scopes_are_counted_apart(async_db):
    responses = _Reader(start=1)
    messages = _Reader(start=9)

    assert await allocate_sequence(async_db, "response", "resp_1", responses) == 1
    assert await allocate_sequence(async_db, "response", "resp_2", responses) == 1
    assert await allocate_sequence(async_db, "thread", "resp_1", messages) == 9
    assert await allocate_sequence(async_db, "response", "resp_1", responses) == 2


@pytest.mark.asyncio
async def test_a_commit_forgets_the_counter_so_the_next_transaction_reads_again(async_db):
    reader = _Reader(start=1)
    await allocate_sequence(async_db, "response", "resp_1", reader)
    await async_db.commit()

    reader.start = 7
    assert await allocate_sequence(async_db, "response", "resp_1", reader) == 7
    assert reader.calls == 2


@pytest.mark.asyncio
async def test_a_rollback_forgets_the_counter(async_db):
    # A real allocation locks the parent row, which opens the transaction the
    # rollback then ends; the fake reader does not, so open one explicitly.
    await async_db.execute(text("SELECT 1"))
    reader = _Reader(start=1)
    await allocate_sequence(async_db, "response", "resp_1", reader)
    await allocate_sequence(async_db, "response", "resp_1", reader)
    await async_db.rollback()

    assert await allocate_sequence(async_db, "response", "resp_1", reader) == 1
    assert reader.calls == 2
