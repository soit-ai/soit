""" transaction

Transaction helpers.
"""

from collections.abc import Generator
from contextlib import contextmanager
from types import TracebackType
from typing import Literal

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.kernel.commons.errors import KernelError


class SQLAlchemyUnitOfWork:
    """SQLAlchemy implementation of the application unit-of-work contract."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def __enter__(self) -> "SQLAlchemyUnitOfWork":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        _ = exc_value, traceback
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        return False

    def commit(self) -> None:
        """Commit all writes staged by the use case."""
        self.db.commit()

    def rollback(self) -> None:
        """Roll back all writes staged by the use case."""
        self.db.rollback()


@contextmanager
def transaction(db: Session) -> Generator[Session, None, None]:
    """Context manager for database transaction.

    Usage:
        with transaction(db) as txn:
            # Do database operations
            txn.add(model)
            txn.commit()

    Args:
        db: Database session.

    Yields:
        Database session (same as input).

    Raises:
        KernelError: If transaction fails and is rolled back.
    """
    try:
        yield db
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        raise KernelError(
            code="DATABASE_ERROR",
            message=f"Transaction failed: {str(e)}",
        ) from e
    except Exception:
        db.rollback()
        raise


@contextmanager
def nested_transaction(db: Session) -> Generator[Session, None, None]:
    """Context manager for nested transaction (savepoint).

    Usage:
        with transaction(db) as txn:
            # Outer transaction
            with nested_transaction(txn) as nested:
                # Nested transaction (savepoint)
                nested.add(model)
                # If exception occurs here, only nested transaction rolls back

    Args:
        db: Database session.

    Yields:
        Database session (same as input).

    Raises:
        KernelError: If nested transaction fails and is rolled back.
    """
    savepoint = db.begin_nested()
    try:
        yield db
        savepoint.commit()
    except SQLAlchemyError as e:
        savepoint.rollback()
        raise KernelError(
            code="DATABASE_ERROR",
            message=f"Nested transaction failed: {str(e)}",
        ) from e
    except Exception:
        savepoint.rollback()
        raise
