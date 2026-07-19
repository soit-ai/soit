import time
from pathlib import Path

import pytest

from app.adapters.storage.fsspec import FsspecStoragePort
from app.kernel.commons.errors import KernelError
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.storage.policy import StoragePolicyGateway
from app.settings.settings import settings


class _FakeS3Filesystem:
    protocol = "s3"

    def __init__(self, *, roots: set[str] | None = None) -> None:
        self.roots = set(roots or set())
        self.makedirs_calls: list[tuple[str, bool]] = []

    def exists(self, path: str) -> bool:
        return path in self.roots

    def makedirs(self, path: str, exist_ok: bool = False) -> None:
        self.makedirs_calls.append((path, exist_ok))
        self.roots.add(path)


def test_fsspec_storage_defaults_to_local_development_path(monkeypatch) -> None:
    monkeypatch.setattr(settings, "storage_url", None)

    storage = FsspecStoragePort()

    assert storage.base_url.startswith("file://")


@pytest.mark.asyncio
async def test_put_get_exists_and_delete_roundtrip(tmp_path: Path) -> None:
    storage = FsspecStoragePort(base_url=tmp_path.as_uri(), auto_mkdir=True)

    key = await storage.put(
        "tenants/t1/workspaces/w1/object.txt",
        b"hello",
        content_type="text/plain",
        metadata={"source": "test"},
    )

    assert key == "tenants/t1/workspaces/w1/object.txt"
    assert await storage.exists(key) is True
    assert await storage.get(key) == b"hello"

    await storage.delete(key)
    assert await storage.exists(key) is False
    await storage.delete(key)


@pytest.mark.asyncio
async def test_delete_uses_single_object_operation(tmp_path: Path, monkeypatch) -> None:
    storage = FsspecStoragePort(base_url=tmp_path.as_uri(), auto_mkdir=True)
    key = await storage.put("single/object.txt", b"hello")

    def fail_bulk_remove(*_args, **_kwargs):
        raise AssertionError("bulk remove must not be used for one object")

    monkeypatch.setattr(storage.fs, "rm", fail_bulk_remove)

    await storage.delete(key)

    assert await storage.exists(key) is False


@pytest.mark.asyncio
@pytest.mark.parametrize("key", ["", "/absolute.txt", "../escape.txt", "safe/../escape.txt"])
async def test_rejects_invalid_keys(tmp_path: Path, key: str) -> None:
    storage = FsspecStoragePort(base_url=tmp_path.as_uri(), auto_mkdir=True)

    with pytest.raises(KernelError):
        await storage.put(key, b"bad")


@pytest.mark.asyncio
async def test_normalizes_backslashes(tmp_path: Path) -> None:
    storage = FsspecStoragePort(base_url=tmp_path.as_uri(), auto_mkdir=True)

    key = await storage.put("nested\\object.txt", b"content")

    assert key == "nested/object.txt"
    assert await storage.get("nested/object.txt") == b"content"


@pytest.mark.asyncio
async def test_get_missing_key_raises_storage_not_found(tmp_path: Path) -> None:
    storage = FsspecStoragePort(base_url=tmp_path.as_uri(), auto_mkdir=True)

    with pytest.raises(KernelError) as exc_info:
        await storage.get("missing.txt")

    assert exc_info.value.code == "STORAGE_NOT_FOUND"


@pytest.mark.asyncio
async def test_storage_operation_timeout_raises_kernel_error(tmp_path: Path, monkeypatch) -> None:
    storage = FsspecStoragePort(
        base_url=tmp_path.as_uri(),
        auto_mkdir=True,
        operation_timeout_seconds=0.01,
    )

    def slow_open(*_args, **_kwargs):
        time.sleep(0.05)
        return None

    monkeypatch.setattr(storage.fs, "open", slow_open)

    with pytest.raises(KernelError) as exc_info:
        await storage.open_writer("slow.txt")

    assert exc_info.value.code == "STORAGE_TIMEOUT"


@pytest.mark.asyncio
async def test_s3_readiness_creates_a_missing_bucket_once(monkeypatch) -> None:
    filesystem = _FakeS3Filesystem()
    monkeypatch.setattr(
        "app.adapters.storage.fsspec.fsspec.core.url_to_fs",
        lambda *_args, **_kwargs: (filesystem, "soit-artifacts/prefix"),
    )
    storage = FsspecStoragePort(base_url="s3://soit-artifacts/prefix", auto_mkdir=True)

    await storage.ensure_ready()
    await storage.ensure_ready()

    assert filesystem.makedirs_calls == [("soit-artifacts", True)]


@pytest.mark.asyncio
async def test_s3_readiness_rejects_a_missing_bucket_when_auto_mkdir_is_disabled(
    monkeypatch,
) -> None:
    filesystem = _FakeS3Filesystem()
    monkeypatch.setattr(
        "app.adapters.storage.fsspec.fsspec.core.url_to_fs",
        lambda *_args, **_kwargs: (filesystem, "soit-artifacts/prefix"),
    )
    storage = FsspecStoragePort(base_url="s3://soit-artifacts/prefix", auto_mkdir=False)

    with pytest.raises(KernelError) as exc_info:
        await storage.ensure_ready()

    assert exc_info.value.code == "STORAGE_NOT_READY"
    assert exc_info.value.details == {"backend": "s3", "root": "soit-artifacts"}


@pytest.mark.asyncio
async def test_storage_backend_errors_are_typed_without_leaking_provider_details(
    tmp_path: Path,
    monkeypatch,
) -> None:
    storage = FsspecStoragePort(base_url=tmp_path.as_uri(), auto_mkdir=True)

    def unavailable(_path: str) -> bool:
        raise RuntimeError("access_key=secret-provider-detail")

    monkeypatch.setattr(storage.fs, "exists", unavailable)

    with pytest.raises(KernelError) as exc_info:
        await storage.exists("object.txt")

    assert exc_info.value.code == "STORAGE_UNAVAILABLE"
    assert exc_info.value.details["operation"] == "storage_ready"
    assert "secret-provider-detail" not in str(exc_info.value.details)
    assert "secret-provider-detail" not in exc_info.value.message


@pytest.mark.asyncio
async def test_streaming_writer_and_reader_roundtrip(tmp_path: Path) -> None:
    storage = FsspecStoragePort(base_url=tmp_path.as_uri(), auto_mkdir=True)

    async with await storage.open_writer("streams/data.bin") as writer:
        assert await writer.write(b"hello ") == 6
        assert await writer.write(b"stream") == 6

    async with await storage.open_reader("streams/data.bin") as reader:
        assert await reader.read(5) == b"hello"
        assert await reader.read() == b" stream"


@pytest.mark.asyncio
async def test_policy_gateway_exposes_streaming_operations(tmp_path: Path) -> None:
    storage = FsspecStoragePort(base_url=tmp_path.as_uri(), auto_mkdir=True)
    gateway = StoragePolicyGateway(
        gateway=storage,
        ctx=RequestContext(
            tenant_id="tenant",
            workspace_id="workspace",
            user_id="user",
            tenant_role="Owner",
            workspace_role="Owner",
        ),
    )

    async with await gateway.open_writer("policy/data.bin") as writer:
        await writer.write(b"policy stream")

    async with await gateway.open_reader("policy/data.bin") as reader:
        assert await reader.read() == b"policy stream"
