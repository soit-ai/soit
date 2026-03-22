""" session

DB engine/session management.
"""

from typing import Generator, Optional
from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, Session

from app.settings.settings import settings


# Global engine instance
_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker] = None


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
            pool_size=10,
            max_overflow=20,
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
