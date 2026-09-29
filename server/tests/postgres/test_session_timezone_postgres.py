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
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from app.infra.db.session import build_async_engine
from app.modules.identity.domain.models import ApiKey

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


@pytest.mark.asyncio
async def test_a_model_reads_both_kinds_of_timestamp_back_as_aware_utc() -> None:
    # api_keys.created_at is a timestamp and expires_at a timestamptz. Read
    # back, one was naive and the other aware, so the lifetime a rotation
    # carries over could not be computed; both are aware UTC now.
    engine = build_async_engine(_database_url())
    token = uuid4().hex
    created = datetime(2026, 9, 1, 8, 0, 0, tzinfo=UTC)
    try:
        async with AsyncSession(engine) as db:
            db.add(
                ApiKey(
                    id=f"key_tz_{token}",
                    tenant_id=f"tz-{token}",
                    workspace_id=f"tz-{token}",
                    user_id="tz-user",
                    name="tz",
                    key_prefix="sk_tz",
                    key_hash=f"tz-hash-{token}",
                    created_at=created,
                    expires_at=created + timedelta(days=30),
                )
            )
            await db.commit()
        async with AsyncSession(engine) as db:
            key = await db.get(ApiKey, f"key_tz_{token}")
            assert key is not None
            assert key.created_at == created
            assert key.created_at.utcoffset() == timedelta(0)
            assert key.expires_at is not None
            assert key.expires_at.utcoffset() == timedelta(0)
            assert (key.expires_at - key.created_at).days == 30
            await db.delete(key)
            await db.commit()
    finally:
        await engine.dispose()
