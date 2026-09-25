"""Which storage adapter the container hands out in test runtimes.

A deterministic test runtime keeps storage in memory unless it names a store
in its environment; a stack whose API and ingest worker are separate
processes needs that shared store, since memory is private to one process.
"""

from __future__ import annotations

import pytest

from app.adapters.storage.fsspec import FsspecStoragePort
from app.adapters.storage.memory import InMemoryStoragePort
from app.wiring.container import Container


def _storage(monkeypatch: pytest.MonkeyPatch, **env: str | None):
    for key, value in env.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    return Container._create_storage_port(Container.__new__(Container))


def test_pytest_always_gets_memory_storage(monkeypatch, tmp_path) -> None:
    storage = _storage(monkeypatch, STORAGE_URL=tmp_path.as_uri())
    assert isinstance(storage, InMemoryStoragePort)


def test_a_test_runtime_without_a_store_gets_memory(monkeypatch) -> None:
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    storage = _storage(monkeypatch, SOIT_TESTING="1", STORAGE_URL=None)
    assert isinstance(storage, InMemoryStoragePort)


def test_a_test_runtime_that_names_a_store_shares_it(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr("app.settings.settings.settings.storage_url", tmp_path.as_uri())
    storage = _storage(monkeypatch, SOIT_TESTING="1", STORAGE_URL=tmp_path.as_uri())
    assert isinstance(storage, FsspecStoragePort)
