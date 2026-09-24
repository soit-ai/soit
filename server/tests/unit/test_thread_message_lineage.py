"""A conversation branch is read from its head down to a window, not from the whole ledger."""

from __future__ import annotations

import pytest
from sqlalchemy import event

from app.kernel.runtime.db.models.threads import Thread, ThreadMessage
from app.kernel.runtime.threads.repository import ThreadRepository

THREAD = "thread_lineage"


async def _seed(async_db, ctx) -> dict[str, ThreadMessage]:
    """A main branch m1..m6 and a sibling branch s3->s4 forking after m2."""
    async_db.add(Thread(id=THREAD, tenant_id=ctx.tenant_id, workspace_id=ctx.workspace_id, title="lineage"))
    messages: dict[str, ThreadMessage] = {}
    parent = None
    sequence = 0
    for name in ("m1", "m2", "m3", "m4", "m5", "m6"):
        sequence += 1
        message = ThreadMessage(
            id=name, tenant_id=ctx.tenant_id, workspace_id=ctx.workspace_id, thread_id=THREAD,
            role="user" if sequence % 2 else "assistant", content=f"{name} text",
            parent_message_id=parent, sequence_no=sequence,
            metadata_json={"agui_message_id": f"agui_{name}"},
        )
        async_db.add(message)
        messages[name] = message
        parent = name
    for name, parent in (("s3", "m2"), ("s4", "s3")):
        sequence += 1
        message = ThreadMessage(
            id=name, tenant_id=ctx.tenant_id, workspace_id=ctx.workspace_id, thread_id=THREAD,
            role="user", content=f"{name} text", parent_message_id=parent, sequence_no=sequence,
        )
        async_db.add(message)
        messages[name] = message
    await async_db.commit()
    return messages


@pytest.fixture
def statements(async_db) -> list[str]:
    seen: list[str] = []

    def record(_conn, _cursor, statement, _parameters, _context, _executemany) -> None:
        seen.append(statement)

    engine = async_db.bind.sync_engine
    event.listen(engine, "before_cursor_execute", record)
    yield seen
    event.remove(engine, "before_cursor_execute", record)


@pytest.mark.asyncio
async def test_lineage_follows_one_branch_root_first_in_one_statement(async_db, ctx, statements) -> None:
    await _seed(async_db, ctx)
    repo = ThreadRepository(async_db, ctx)
    statements.clear()

    main = await repo.message_lineage(THREAD, "m6")
    sibling = await repo.message_lineage(THREAD, "s4")

    assert [m.id for m in main] == ["m1", "m2", "m3", "m4", "m5", "m6"]
    assert [m.id for m in sibling] == ["m1", "m2", "s3", "s4"]
    assert len([s for s in statements if "thread_messages" in s]) == 2


@pytest.mark.asyncio
async def test_the_window_keeps_the_newest_messages(async_db, ctx) -> None:
    await _seed(async_db, ctx)
    repo = ThreadRepository(async_db, ctx)

    assert [m.id for m in await repo.message_lineage(THREAD, "m6", limit=3)] == ["m4", "m5", "m6"]
    assert [m.id for m in await repo.message_lineage(THREAD, "m6", limit=1)] == ["m6"]


@pytest.mark.asyncio
async def test_an_unknown_head_or_a_dangling_parent_is_refused(async_db, ctx) -> None:
    messages = await _seed(async_db, ctx)
    repo = ThreadRepository(async_db, ctx)

    with pytest.raises(ValueError, match="unknown message"):
        await repo.message_lineage(THREAD, "nope")

    messages["m3"].parent_message_id = "gone"
    async_db.add(messages["m3"])
    await async_db.commit()
    with pytest.raises(ValueError, match="unknown message"):
        await repo.message_lineage(THREAD, "m6")
    # A window that ends before the dangling link is still served.
    assert [m.id for m in await repo.message_lineage(THREAD, "m6", limit=3)] == ["m4", "m5", "m6"]


@pytest.mark.asyncio
async def test_a_cycle_is_refused(async_db, ctx) -> None:
    messages = await _seed(async_db, ctx)
    messages["m1"].parent_message_id = "m3"
    async_db.add(messages["m1"])
    await async_db.commit()

    with pytest.raises(ValueError, match="cycle"):
        await ThreadRepository(async_db, ctx).message_lineage(THREAD, "m6")


@pytest.mark.asyncio
async def test_latest_and_agui_lookups_do_not_list_the_ledger(async_db, ctx, statements) -> None:
    await _seed(async_db, ctx)
    repo = ThreadRepository(async_db, ctx)
    statements.clear()

    assert await repo.latest_message_id(THREAD) == "s4"
    found = await repo.find_by_agui_message_id(THREAD, "agui_m4")
    assert found is not None and found.id == "m4"
    assert await repo.find_by_agui_message_id(THREAD, "agui_none") is None
    assert all("LIMIT" in s.upper() for s in statements if "thread_messages" in s)
