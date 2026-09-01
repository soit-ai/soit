"""MILVUS_MODE switches the vector adapter between a Milvus server and Milvus Lite."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

import app.adapters.vector.milvus as milvus_mod
from app.adapters.vector.milvus import MilvusVectorPort
from app.kernel.commons.errors import KernelError
from app.settings.settings import Settings


def _connected(monkeypatch) -> MagicMock:
    """Stub the connection layer as disconnected and record connect calls."""
    connect = MagicMock()
    monkeypatch.setattr(milvus_mod.connections, "connect", connect)
    monkeypatch.setattr(milvus_mod.connections, "has_connection", MagicMock(return_value=False))
    return connect


def test_server_mode_connects_to_host_and_port(monkeypatch):
    connect = _connected(monkeypatch)
    MilvusVectorPort(host="milvus", port=19530, mode="server")._ensure_connected()
    connect.assert_called_once_with("default", host="milvus", port=19530)


def test_lite_mode_connects_to_a_local_file(monkeypatch, tmp_path):
    connect = _connected(monkeypatch)
    monkeypatch.setattr(milvus_mod.sys, "platform", "linux")
    lite_file = tmp_path / "nested" / "soit_lite.db"

    MilvusVectorPort(mode="lite", lite_file=str(lite_file))._ensure_connected()

    connect.assert_called_once_with("default", uri=str(lite_file))
    # The parent directory is created for the caller; pymilvus refuses a
    # missing one.
    assert lite_file.parent.is_dir()


def test_lite_mode_rejects_a_path_that_is_not_a_database_file(monkeypatch, tmp_path):
    _connected(monkeypatch)
    monkeypatch.setattr(milvus_mod.sys, "platform", "linux")
    port = MilvusVectorPort(mode="lite", lite_file=str(tmp_path / "soit_lite"))

    with pytest.raises(KernelError) as excinfo:
        port._ensure_connected()

    assert excinfo.value.code == "VECTOR_LITE_UNSUPPORTED"


def test_lite_mode_reports_that_windows_has_no_build(monkeypatch, tmp_path):
    _connected(monkeypatch)
    monkeypatch.setattr(milvus_mod.sys, "platform", "win32")
    port = MilvusVectorPort(mode="lite", lite_file=str(tmp_path / "soit_lite.db"))

    with pytest.raises(KernelError) as excinfo:
        port._ensure_connected()

    assert excinfo.value.code == "VECTOR_LITE_UNSUPPORTED"
    assert "WSL" in excinfo.value.message


def test_lite_mode_indexes_flat_because_milvus_lite_has_nothing_else():
    lite = MilvusVectorPort(mode="lite", lite_file="./x.db")._index_params("COSINE")
    server = MilvusVectorPort(mode="server")._index_params("COSINE")

    assert lite == {"index_type": "FLAT", "metric_type": "COSINE", "params": {}}
    assert server["index_type"] == "IVF_FLAT"
    assert server["params"] == {"nlist": 1024}


def test_mode_defaults_to_server_for_instances_built_without_init():
    # Adapter tests construct the port without __init__; the class defaults keep
    # server behaviour in that case.
    assert object.__new__(MilvusVectorPort).mode == "server"


def test_settings_reject_an_unknown_mode():
    with pytest.raises(ValueError, match="MILVUS_MODE"):
        Settings(milvus_mode="sqlite", _env_file=None)


def test_settings_normalize_mode_case():
    assert Settings(milvus_mode="Lite", _env_file=None).milvus_mode == "lite"


def test_production_refuses_milvus_lite():
    settings = Settings(
        _env_file=None,
        environment="production",
        database_url="postgresql://soit:secret@db.internal:5432/soit",
        event_bus_backend="redis",
        milvus_mode="lite",
    )
    with pytest.raises(ValueError, match="Milvus Lite"):
        settings.validate_runtime_requirements()


def test_lite_file_default_is_relative_to_the_server_process():
    assert not Path(Settings(_env_file=None).milvus_lite_file).is_absolute()
