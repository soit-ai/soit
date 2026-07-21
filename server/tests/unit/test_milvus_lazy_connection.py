"""Milvus adapter connects lazily, not at construction (graceful degradation)."""

from unittest.mock import MagicMock

import pytest

import app.adapters.vector.milvus as milvus_mod
from app.adapters.vector.milvus import MilvusVectorPort


def test_construction_does_not_connect(monkeypatch):
    connect = MagicMock()
    monkeypatch.setattr(milvus_mod.connections, "connect", connect)
    # Constructing the port during DI must not touch the network.
    MilvusVectorPort(host="milvus", port=19530)
    connect.assert_not_called()


def test_ensure_connected_skips_when_already_connected(monkeypatch):
    connect = MagicMock()
    monkeypatch.setattr(milvus_mod.connections, "connect", connect)
    monkeypatch.setattr(milvus_mod.connections, "has_connection", MagicMock(return_value=True))
    MilvusVectorPort()._ensure_connected()
    connect.assert_not_called()


def test_ensure_connected_connects_when_absent(monkeypatch):
    connect = MagicMock()
    monkeypatch.setattr(milvus_mod.connections, "connect", connect)
    monkeypatch.setattr(milvus_mod.connections, "has_connection", MagicMock(return_value=False))
    MilvusVectorPort()._ensure_connected()
    connect.assert_called_once()


@pytest.mark.asyncio
async def test_check_ready_connects_and_probes(monkeypatch):
    connect = MagicMock()
    get_version = MagicMock(return_value="2.5.11")
    monkeypatch.setattr(milvus_mod.connections, "connect", connect)
    monkeypatch.setattr(milvus_mod.connections, "has_connection", MagicMock(return_value=False))
    monkeypatch.setattr(milvus_mod.utility, "get_server_version", get_version)
    await MilvusVectorPort().check_ready()
    connect.assert_called_once()
    get_version.assert_called_once()
