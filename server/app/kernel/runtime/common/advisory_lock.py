"""Transaction-scoped advisory locks for serialising writers on a logical key.

Some invariants span rows that no single row lock covers, such as a running
balance summed over a ledger. Writers that read such an aggregate and act on
it must hold ``acquire_xact_lock`` for the same key, so the read and the write
happen as one serial step. The lock is released when the surrounding
transaction commits or rolls back.

PostgreSQL provides the lock through ``pg_advisory_xact_lock``. Other dialects
(SQLite in unit tests) serialise writers at the database level already, so the
helper is a no-op there.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession


def _dialect_name(db: AsyncSession) -> str:
    bind = db.get_bind()
    return bind.dialect.name


async def acquire_xact_lock(db: AsyncSession, *parts: str) -> None:
    """Block until this transaction holds the advisory lock for ``parts``."""

    if _dialect_name(db) != "postgresql":
        return
    key = ":".join(parts)
    await db.exec(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))").bindparams(key=key)
    )
