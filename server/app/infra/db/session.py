""" session

DB engine/session management.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

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


def get_async_engine() -> AsyncEngine:
    """Get or create the async database engine."""
    global _async_engine
    if _async_engine is None:
        database_url = _async_database_url(settings.database_url or "")
        if database_url.startswith("sqlite"):
            _async_engine = create_async_engine(database_url, echo=False)
        else:
            _async_engine = create_async_engine(
                database_url,
                echo=False,
                pool_pre_ping=True,
                pool_size=_POOL_SIZE,
                max_overflow=_MAX_OVERFLOW,
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


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async session inside a unit of work."""
    session = get_async_session_local()()
    try:
        from app.infra.db.transaction import AsyncSQLAlchemyUnitOfWork

        async with AsyncSQLAlchemyUnitOfWork(session):
            yield session
    finally:
        await session.close()


async def dispose_async_engine() -> None:
    """Release the async engine's pooled connections (process shutdown, tests)."""
    global _async_engine, _AsyncSessionLocal
    if _async_engine is not None:
        await _async_engine.dispose()
    _async_engine = None
    _AsyncSessionLocal = None
