""" transaction

Transaction helpers.
"""

from contextlib import contextmanager
from typing import Generator
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.kernel.commons.errors import KernelError


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
    except Exception as e:
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
    except Exception as e:
        savepoint.rollback()
        raise
