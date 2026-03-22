""" memory_storage

In-memory storage port for tests and lightweight workflows.
"""

from typing import Optional, Dict, Tuple, Any

from app.kernel.ports.storage.interface import StoragePort


class InMemoryStoragePort(StoragePort):
    """In-memory object storage implementation."""

    def __init__(self, bucket: Optional[str] = "in-memory"):
        self._bucket = bucket or "in-memory"
        self._store: Dict[Tuple[str, str], bytes] = {}

    async def put(
        self,
        key: str,
        data: bytes,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> str:
        self._store[(self._bucket, key)] = data
        return key

    async def get(self, key: str, **kwargs: Any) -> bytes:
        return self._store[(self._bucket, key)]

    async def delete(self, key: str, **kwargs: Any) -> None:
        self._store.pop((self._bucket, key), None)

    async def exists(self, key: str, **kwargs: Any) -> bool:
        return (self._bucket, key) in self._store
