"""The application engine stores naive UTC whatever the server's time zone.

Timestamp columns are ``timestamp without time zone`` holding UTC, and the app
writes aware ``utc_now()`` values. psycopg renders an aware datetime in the
*session* time zone before the column drops the offset, so on a server whose
default zone is not UTC (a Windows installer picks the machine's zone) every
write would land shifted by that offset unless the engine pins the session.
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from app.infra.db.session import build_async_engine

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url.startswith("postgresql"):
        pytest.skip("DATABASE_URL does not point to PostgreSQL")
    return url


@pytest.mark.asyncio
async def test_engine_pins_the_session_time_zone_to_utc() -> None:
    engine = build_async_engine(_database_url())
    try:
        async with engine.connect() as conn:
            zone = (await conn.execute(text("SHOW timezone"))).scalar_one()
            assert zone == "UTC"

            await conn.execute(
                text("CREATE TEMP TABLE tz_probe (at timestamp without time zone)")
            )
            written = datetime(2026, 9, 23, 17, 0, 0, tzinfo=UTC)
            await conn.execute(text("INSERT INTO tz_probe (at) VALUES (:at)"), {"at": written})
            stored = (await conn.execute(text("SELECT at FROM tz_probe"))).scalar_one()
            assert stored == written.replace(tzinfo=None)
    finally:
        await engine.dispose()
