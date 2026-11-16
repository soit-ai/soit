"""PostgreSQL enforces the engine's timeout backstops on pooled connections."""

from __future__ import annotations

import asyncio
import os
import sys

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.infra.db import session as db_session

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url.startswith("postgresql"):
        pytest.skip("DATABASE_URL does not point to PostgreSQL")
    return url


@pytest.mark.asyncio
async def test_a_runaway_statement_is_cancelled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db_session.settings, "database_statement_timeout_ms", 200)
    engine = db_session.build_async_engine(_database_url())
    try:
        async with engine.connect() as conn:
            with pytest.raises(DBAPIError, match="statement timeout"):
                await conn.execute(text("SELECT pg_sleep(2)"))
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_a_forgotten_transaction_is_ended(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db_session.settings, "database_idle_in_transaction_timeout_ms", 300)
    engine = db_session.build_async_engine(_database_url())
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            await asyncio.sleep(1.0)
            with pytest.raises(DBAPIError):
                await conn.execute(text("SELECT 1"))
        # The pool replaces the ended connection.
        async with engine.connect() as conn:
            assert (await conn.execute(text("SELECT 1"))).scalar_one() == 1
    finally:
        await engine.dispose()
