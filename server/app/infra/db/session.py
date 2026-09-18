""" session

DB engine/session management.
"""

from collections.abc import AsyncGenerator
from typing import Any

import orjson
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.requests import HTTPConnection

from app.settings.settings import settings

# Async engine and session factory: the only database stack the app uses.
_async_engine: AsyncEngine | None = None
_AsyncSessionLocal: async_sessionmaker[AsyncSession] | None = None

# Pool sizing comes from settings so an operator can size the
# per-process connection budget against
# PostgreSQL's max_connections (see docs/operations/database-connections.md).
_POOL_SIZE = settings.database_pool_size
_MAX_OVERFLOW = settings.database_max_overflow


def _async_database_url(url: str) -> str:
    """Map a configured database URL onto its async driver.

    PostgreSQL keeps psycopg (v3), which serves both the sync and the async
    engine. SQLite switches to aiosqlite so the test fixtures can run the
    async stack in-process.
    """
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("sqlite://") and "+aiosqlite" not in url:
        return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    return url


def json_column_serializer(value: Any) -> str:
    """Encode a JSON column with orjson.

    An agent execution writes a dozen JSON columns; orjson encodes them several
    times faster than the stdlib and accepts a superset of its input.
    OPT_NON_STR_KEYS keeps the stdlib's habit of writing int keys as strings,
    which stored payloads rely on.
    """
    return orjson.dumps(value, option=orjson.OPT_NON_STR_KEYS).decode()


def get_async_engine() -> AsyncEngine:
    """Get or create the async database engine."""
    global _async_engine
    if _async_engine is None:
        database_url = _async_database_url(settings.database_url or "")
        if database_url.startswith("sqlite"):
            _async_engine = create_async_engine(
                database_url,
                echo=False,
                json_serializer=json_column_serializer,
                json_deserializer=orjson.loads,
            )
        else:
            _async_engine = create_async_engine(
                database_url,
                echo=False,
                pool_pre_ping=True,
                pool_size=_POOL_SIZE,
                max_overflow=_MAX_OVERFLOW,
                json_serializer=json_column_serializer,
                json_deserializer=orjson.loads,
            )
    return _async_engine


def get_async_session_local() -> async_sessionmaker[AsyncSession]:
    """Get or create the async session factory.

    `expire_on_commit=False` is deliberate: with an async session every
    attribute refresh is real IO, and an implicit one after commit raises
    `MissingGreenlet`. Callers that need fresh state call `await
    session.refresh(obj)` explicitly.
    """
    global _AsyncSessionLocal
    if _AsyncSessionLocal is None:
        _AsyncSessionLocal = async_sessionmaker(
            bind=get_async_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _AsyncSessionLocal


# Where `get_async_db` parks the request's session so `commit_unit_of_work`
# can reach it without being part of the same dependency chain.
UNIT_OF_WORK_STATE_KEY = "unit_of_work_session"


async def get_async_db(connection: HTTPConnection) -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding the request's async session inside a unit of work.

    This dependency is request-scoped on purpose: FastAPI runs its exit code
    after the response has been sent, which is what a streaming route needs
    because its body generator reads through this same session. The commit
    that must land before the response is `commit_unit_of_work`'s job; the
    exit here only commits what a streaming body wrote afterwards, rolls back
    on error, and closes the session.
    """
    session = get_async_session_local()()
    setattr(connection.state, UNIT_OF_WORK_STATE_KEY, session)
    try:
        from app.infra.db.transaction import AsyncSQLAlchemyUnitOfWork

        async with AsyncSQLAlchemyUnitOfWork(session):
            yield session
    finally:
        await session.close()


async def commit_unit_of_work(connection: HTTPConnection) -> AsyncGenerator[None, None]:
    """Commit the request's unit of work when the handler returns, before the response is sent.

    Installed app-wide as ``Depends(commit_unit_of_work, scope="function")``.
    A function-scoped dependency's exit code runs before FastAPI sends the
    response, so a client that reads its 201 and immediately uses the row on
    another API worker finds it committed; handlers and repositories only
    flush, and the request-scoped commit in `get_async_db` would land after
    the response. A request that never resolved `get_async_db` has nothing to
    commit, and a handler that raised skips the commit so `get_async_db`
    rolls back instead.
    """
    yield
    session: AsyncSession | None = getattr(connection.state, UNIT_OF_WORK_STATE_KEY, None)
    if session is not None:
        from app.infra.db.transaction import AsyncSQLAlchemyUnitOfWork

        await AsyncSQLAlchemyUnitOfWork(session).commit()


async def dispose_async_engine() -> None:
    """Release the async engine's pooled connections (process shutdown, tests)."""
    global _async_engine, _AsyncSessionLocal
    if _async_engine is not None:
        await _async_engine.dispose()
    _async_engine = None
    _AsyncSessionLocal = None
