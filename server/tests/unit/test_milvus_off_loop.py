"""The Milvus adapter keeps its blocking gRPC calls off the event loop."""

from __future__ import annotations

import threading
from typing import Any

import pytest

import app.adapters.vector.milvus as milvus_module
from app.adapters.vector.milvus import MilvusVectorPort


class _Connections:
    @staticmethod
    def has_connection(_alias: str) -> bool:
        return True


class _Result:
    ids = ["vec-1"]
    distances = [0.5]

    def __iter__(self):
        return iter([])


@pytest.fixture
def milvus(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    state: dict[str, Any] = {"threads": [], "loads": 0, "searches": 0, "fail_next_search": False}

    class _Utility:
        @staticmethod
        def has_collection(_name: str) -> bool:
            state["threads"].append(threading.get_ident())
            return True

    class _Collection:
        def __init__(self, name: str, schema: Any = None) -> None:
            del schema
            self.name = name

        def load(self) -> None:
            state["loads"] += 1

        def search(self, **_kwargs: Any) -> list[_Result]:
            state["threads"].append(threading.get_ident())
            state["searches"] += 1
            if state["fail_next_search"]:
                state["fail_next_search"] = False
                raise RuntimeError("collection not loaded")
            return [_Result()]

        def insert(self, _data: Any) -> None:
            state["threads"].append(threading.get_ident())

        def flush(self) -> None:
            return None

        def delete(self, _expr: str) -> None:
            state["threads"].append(threading.get_ident())

    monkeypatch.setattr(milvus_module, "connections", _Connections)
    monkeypatch.setattr(milvus_module, "utility", _Utility)
    monkeypatch.setattr(milvus_module, "Collection", _Collection)
    monkeypatch.setattr(milvus_module, "_loaded_collections", set())
    return state


@pytest.mark.asyncio
async def test_calls_run_on_a_worker_thread_and_load_once(milvus: dict[str, Any]) -> None:
    port = MilvusVectorPort(mode="server", host="milvus", port=19530)
    loop_thread = threading.get_ident()

    await port.query("kb:one", [0.1, 0.2], top_k=1)
    await port.query("kb:one", [0.1, 0.2], top_k=1)
    await port.delete("kb:one", ["vec-1"])

    assert milvus["threads"]
    assert loop_thread not in milvus["threads"]
    assert milvus["loads"] == 1


@pytest.mark.asyncio
async def test_a_released_collection_is_loaded_again(milvus: dict[str, Any]) -> None:
    port = MilvusVectorPort(mode="server", host="milvus", port=19530)
    await port.query("kb:two", [0.1], top_k=1)
    milvus["fail_next_search"] = True

    result = await port.query("kb:two", [0.1], top_k=1)

    assert result.ids == ["vec-1"]
    assert milvus["loads"] == 2
    assert milvus["searches"] == 3
