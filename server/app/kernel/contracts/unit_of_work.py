"""Stable unit-of-work contract for application use cases."""

from types import TracebackType
from typing import Protocol, Self


class UnitOfWork(Protocol):
    """Own one application transaction boundary."""

    def __enter__(self) -> Self:
        """Enter the transaction boundary."""
        ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        """Commit success or roll back failure."""
        ...

    def commit(self) -> None:
        """Commit staged changes."""
        ...

    def rollback(self) -> None:
        """Roll back staged changes."""
        ...
