""" transaction

Transaction helpers.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from types import TracebackType
from typing import Literal

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.commons.errors import KernelError


@asynccontextmanager
async def async_transaction(db: AsyncSession) -> AsyncGenerator[AsyncSession, None]:
    """Async counterpart of `transaction` for `AsyncSession`."""
    try:
        yield db
        await db.commit()
    except SQLAlchemyError as e:
        await db.rollback()
        raise KernelError(
            code="DATABASE_ERROR",
            message=f"Transaction failed: {str(e)}",
        ) from e
    except Exception:
        await db.rollback()
        raise


class AsyncSQLAlchemyUnitOfWork:
    """Async counterpart of `SQLAlchemyUnitOfWork` for `AsyncSession`."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def __aenter__(self) -> "AsyncSQLAlchemyUnitOfWork":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        _ = exc_value, traceback
        if exc_type is None and self.db.is_active:
            await self.commit()
        else:
            # An exception, or a transaction already broken inside the block:
            # a streaming response whose client disconnected cancels the query
            # in flight, which leaves the session needing a rollback, and a
            # commit there would raise PendingRollbackError over a request
            # that has already been answered.
            await self.rollback()
        return False

    async def commit(self) -> None:
        """Commit all writes staged by the use case."""
        await self.db.commit()

    async def rollback(self) -> None:
        """Roll back all writes staged by the use case."""
        await self.db.rollback()
