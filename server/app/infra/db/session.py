""" session

DB engine/session management.
"""

from collections.abc import AsyncGenerator, Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.settings.settings import settings

# Global engine instance
_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None

# Async engine and session factory (the target stack; the sync pair above
# stays only until every caller has moved over).
_async_engine: AsyncEngine | None = None
_AsyncSessionLocal: async_sessionmaker[AsyncSession] | None = None

# Pool sizing is shared by both engines and comes from settings so an
# operator can size the per-process connection budget against
# PostgreSQL's max_connections (see docs/operations/database-connections.md).
_POOL_SIZE = settings.database_pool_size
_MAX_OVERFLOW = settings.database_max_overflow


def get_engine() -> Engine:
    """Get or create database engine.

    Returns:
        SQLAlchemy engine instance.
    """
    global _engine
    if _engine is None:
        database_url = settings.database_url
        # Prefer psycopg (v3) driver when using PostgreSQL.
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        # Use echo=True for SQL logging in development
        _engine = create_engine(
            database_url,
            echo=False,
            pool_pre_ping=True,
            pool_size=_POOL_SIZE,
            max_overflow=_MAX_OVERFLOW,
        )
    return _engine


def get_session_local() -> sessionmaker:
    """Get or create session factory.

    Returns:
        Session factory.
    """
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine()
        _SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=engine,
            class_=Session,
        )
    return _SessionLocal


def create_tables() -> None:
    """Create all database tables.

    This should be called after all models are imported.
    """
    engine = get_engine()
    SQLModel.metadata.create_all(engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency for FastAPI to get database session.

    Yields:
        Database session.
    """
    SessionLocal = get_session_local()
    db = SessionLocal()
    try:
        from app.infra.db.transaction import SQLAlchemyUnitOfWork

        with SQLAlchemyUnitOfWork(db):
            yield db
    finally:
        db.close()


def get_db_sync() -> Session:
    """Get a synchronous database session (for non-async contexts).

    Returns:
        Database session.
    """
    SessionLocal = get_session_local()
    return SessionLocal()


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
