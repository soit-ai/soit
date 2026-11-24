"""The knowledge service refuses an oversized upload as it streams it to storage."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.kernel.commons.errors import ValidationError
from app.modules.knowledge.application.runtime_service import KnowledgeRuntimeService
from app.settings.settings import settings


class _Stream:
    def __init__(self, data: bytes) -> None:
        self._data = data

    async def read(self, size: int = -1) -> bytes:
        chunk, self._data = self._data[:size], self._data[size:]
        return chunk


class _Writer:
    def __init__(self, store: _Storage, key: str) -> None:
        self.store, self.key = store, key

    async def __aenter__(self):
        self.store.objects[self.key] = b""
        return self

    async def __aexit__(self, *exc) -> None:
        return None

    async def write(self, chunk: bytes) -> None:
        self.store.objects[self.key] += chunk


class _Storage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def open_writer(self, *, key: str, **_kwargs):
        return _Writer(self, key)

    async def delete(self, *, key: str, **_kwargs) -> None:
        self.objects.pop(key, None)


@pytest.mark.asyncio
async def test_a_stream_past_the_limit_is_refused_and_its_partial_object_removed(monkeypatch) -> None:
    monkeypatch.setattr(settings, "knowledge_upload_max_bytes", 1024)
    monkeypatch.setattr("app.modules.knowledge.application.runtime_service.UPLOAD_STREAM_CHUNK_SIZE", 512)
    service = SimpleNamespace(storage_port=_Storage(), _read_upload_chunk=KnowledgeRuntimeService._read_upload_chunk)

    with pytest.raises(ValidationError, match="upload limit"):
        await KnowledgeRuntimeService._stream_upload_to_storage(
            service, "raw/key", _Stream(b"x" * 4096), content_type="text/plain", run_id=None
        )
    assert service.storage_port.objects == {}
