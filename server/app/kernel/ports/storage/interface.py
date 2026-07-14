""" interface

Object storage port interface.
"""

from abc import ABC, abstractmethod
from typing import Any, Protocol, runtime_checkable


class StoragePort(ABC):
    """Object storage port interface."""

    @abstractmethod
    async def put(
        self,
        key: str,
        data: bytes,
        content_type: str | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> str:
        """Upload object.

        Args:
            key: Storage key (path).
            data: Object data.
            content_type: Optional content type.
            metadata: Optional metadata.
            **kwargs: Additional parameters.

        Returns:
            Storage key (same as input or modified).
        """
        pass

    @abstractmethod
    async def get(
        self,
        key: str,
        **kwargs: Any,
    ) -> bytes:
        """Download object.

        Args:
            key: Storage key.
            **kwargs: Additional parameters.

        Returns:
            Object data.
        """
        pass

    @abstractmethod
    async def delete(
        self,
        key: str,
        **kwargs: Any,
    ) -> None:
        """Delete object.

        Args:
            key: Storage key.
            **kwargs: Additional parameters.
        """
        pass

    @abstractmethod
    async def exists(
        self,
        key: str,
        **kwargs: Any,
    ) -> bool:
        """Check if object exists.

        Args:
            key: Storage key.
            **kwargs: Additional parameters.

        Returns:
            True if exists.
        """
        pass


@runtime_checkable
class StorageReader(Protocol):
    """Streaming object reader."""

    async def read(self, size: int = -1) -> bytes:
        """Read bytes from storage."""
        ...

    async def close(self) -> None:
        """Close the reader."""
        ...

    async def __aenter__(self) -> "StorageReader":
        """Enter async context."""
        ...

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        """Exit async context."""
        ...


@runtime_checkable
class StorageWriter(Protocol):
    """Streaming object writer."""

    async def write(self, data: bytes) -> int:
        """Write bytes to storage."""
        ...

    async def close(self) -> None:
        """Close the writer."""
        ...

    async def __aenter__(self) -> "StorageWriter":
        """Enter async context."""
        ...

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        """Exit async context."""
        ...


class StreamingStoragePort(StoragePort):
    """Storage port with streaming reader and writer support."""

    @abstractmethod
    async def open_reader(self, key: str, **kwargs: Any) -> StorageReader:
        """Open a streaming reader for an object."""
        pass

    @abstractmethod
    async def open_writer(
        self,
        key: str,
        content_type: str | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> StorageWriter:
        """Open a streaming writer for an object."""
        pass
