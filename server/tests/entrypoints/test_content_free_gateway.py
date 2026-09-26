"""With content capture off, a gateway call leaves no trace of its text anywhere."""

from __future__ import annotations

import dataclasses

import pytest
from sqlalchemy import select
from sqlmodel import SQLModel

from app.kernel.contracts.context import RequestContext
from app.main import app
from app.middleware.auth import get_current_context
from app.modules.identity.domain.models import Workspace

SECRET = "patient-7731 reports chest pain"


async def _everything_stored(async_db) -> str:
    """Every row of every table, as text."""
    chunks: list[str] = []
    connection = await async_db.connection()
    for table in SQLModel.metadata.sorted_tables:
        rows = (await connection.execute(select(table))).all()
        chunks.extend(repr(tuple(row)) for row in rows)
    return "\n".join(chunks)


async def _call(async_client, *, stream: bool = False) -> None:
    response = await async_client.post(
        "/v1/chat/completions",
        json={
            "model": "model:test:chat",
            "messages": [{"role": "user", "content": SECRET}],
            "stream": stream,
        },
    )
    assert response.status_code == 200
    # The caller still gets the answer; only the record is content-free.
    assert SECRET in response.text


@pytest.mark.asyncio
async def test_a_full_workspace_keeps_the_text(async_client, async_db) -> None:
    await _call(async_client)

    assert SECRET in await _everything_stored(async_db)


@pytest.mark.asyncio
async def test_a_metadata_only_key_leaves_no_text_in_the_database(
    async_client, async_db, ctx: RequestContext
) -> None:
    keyed = dataclasses.replace(ctx, api_key_id="key_private", content_capture="metadata_only")
    app.dependency_overrides[get_current_context] = lambda: keyed
    try:
        await _call(async_client)
        await _call(async_client, stream=True)
        failed = await async_client.post(
            "/v1/chat/completions",
            json={
                "model": "model:test:chat",
                "messages": [
                    {"role": "user", "content": SECRET},
                    {
                        "role": "assistant",
                        "tool_calls": [
                            {"id": "c1", "function": {"name": "f", "arguments": SECRET}}
                        ],
                    },
                ],
            },
        )
        assert failed.status_code == 400
    finally:
        app.dependency_overrides[get_current_context] = lambda: ctx

    stored = await _everything_stored(async_db)
    assert "withheld" in stored
    assert SECRET not in stored


@pytest.mark.asyncio
async def test_a_metadata_only_workspace_applies_without_a_resolved_context(
    async_client, async_db, ctx: RequestContext
) -> None:
    # The context the test client authenticates with carries no mode, as a
    # worker's own context does not; the workspace setting decides.
    async_db.add(
        Workspace(
            id=ctx.workspace_id,
            tenant_id=ctx.tenant_id,
            name="private workspace",
            content_capture="metadata_only",
        )
    )
    await async_db.commit()

    await _call(async_client)

    assert SECRET not in await _everything_stored(async_db)
