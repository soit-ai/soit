"""fsspec storage adapter.

This adapter provides object-storage semantics over fsspec-compatible
filesystems. Business callers continue to use relative object keys.
"""

import asyncio
import json
from pathlib import Path, PurePosixPath
from typing import Any

import fsspec

from app.kernel.commons.errors import KernelError
from app.kernel.ports.storage.interface import (
    StorageReader,
    StorageWriter,
    StreamingStoragePort,
)
from app.settings.settings import settings


async def _run_sync_operation(operation_name: str, timeout_seconds: float | None, func: Any, *args: Any, **kwargs: Any) -> Any:
    try:
        operation = asyncio.to_thread(func, *args, **kwargs)
        if timeout_seconds and timeout_seconds > 0:
            return await asyncio.wait_for(operation, timeout=timeout_seconds)
        return await operation
    except TimeoutError as exc:
        raise KernelError(
            "STORAGE_TIMEOUT",
            f"Storage operation timed out: {operation_name}",
            {"operation": operation_name, "timeout_seconds": timeout_seconds},
        ) from exc


class _AsyncFileReader:
    """Async wrapper for a synchronous fsspec file object."""

    def __init__(self, file_obj: Any, operation_timeout_seconds: float | None):
        self._file_obj = file_obj
        self._operation_timeout_seconds = operation_timeout_seconds

    async def read(self, size: int = -1) -> bytes:
        return await _run_sync_operation("read", self._operation_timeout_seconds, self._file_obj.read, size)

    async def close(self) -> None:
        await _run_sync_operation("close", self._operation_timeout_seconds, self._file_obj.close)

    async def __aenter__(self) -> StorageReader:
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.close()


class _AsyncFileWriter:
    """Async wrapper for a synchronous fsspec file object."""

    def __init__(self, file_obj: Any, operation_timeout_seconds: float | None):
        self._file_obj = file_obj
        self._operation_timeout_seconds = operation_timeout_seconds

    async def write(self, data: bytes) -> int:
        return await _run_sync_operation("write", self._operation_timeout_seconds, self._file_obj.write, data)

    async def close(self) -> None:
        await _run_sync_operation("close", self._operation_timeout_seconds, self._file_obj.close)

    async def __aenter__(self) -> StorageWriter:
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.close()


class FsspecStoragePort(StreamingStoragePort):
    """fsspec-backed storage port."""

    def __init__(
        self,
        base_url: str | None = None,
        storage_options: dict[str, Any] | None = None,
        auto_mkdir: bool | None = None,
        operation_timeout_seconds: float | None = None,
    ):
        self.base_url = base_url or settings.storage_url or self._default_local_base_url()
        self.storage_options = self._normalize_storage_options(
            storage_options if storage_options is not None else self._load_storage_options()
        )
        self.auto_mkdir = settings.storage_auto_mkdir if auto_mkdir is None else auto_mkdir
        self.operation_timeout_seconds = (
            settings.storage_operation_timeout_seconds
            if operation_timeout_seconds is None
            else operation_timeout_seconds
        )
        self.fs, root_path = fsspec.core.url_to_fs(self.base_url, **self.storage_options)
        self.root_path = self._normalize_root_path(root_path)

    @staticmethod
    def _default_local_base_url() -> str:
        return (Path(__file__).resolve().parents[3] / ".soit" / "storage").as_uri()

    async def put(
        self,
        key: str,
        data: bytes,
        content_type: str | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> str:
        normalized_key = self._normalize_key(key)
        async with await self.open_writer(
            normalized_key,
            content_type=content_type,
            metadata=metadata,
            **kwargs,
        ) as writer:
            await writer.write(data)
        return normalized_key

    async def get(self, key: str, **kwargs: Any) -> bytes:
        async with await self.open_reader(key, **kwargs) as reader:
            return await reader.read()

    async def delete(self, key: str, **kwargs: Any) -> None:
        normalized_key = self._normalize_key(key)
        path = self._resolve_path(normalized_key)
        exists = await _run_sync_operation("exists", self.operation_timeout_seconds, self.fs.exists, path)
        if exists:
            await _run_sync_operation("delete", self.operation_timeout_seconds, self.fs.rm, path)

    async def exists(self, key: str, **kwargs: Any) -> bool:
        normalized_key = self._normalize_key(key)
        path = self._resolve_path(normalized_key)
        return await _run_sync_operation("exists", self.operation_timeout_seconds, self._is_file, path)

    async def open_reader(self, key: str, **kwargs: Any) -> StorageReader:
        normalized_key = self._normalize_key(key)
        path = self._resolve_path(normalized_key)
        exists = await _run_sync_operation("exists", self.operation_timeout_seconds, self._is_file, path)
        if not exists:
            raise KernelError(
                "STORAGE_NOT_FOUND",
                f"Storage object not found: {normalized_key}",
                {"key": normalized_key},
            )
        file_obj = await _run_sync_operation("open_reader", self.operation_timeout_seconds, self.fs.open, path, "rb")
        return _AsyncFileReader(file_obj, self.operation_timeout_seconds)

    async def open_writer(
        self,
        key: str,
        content_type: str | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> StorageWriter:
        normalized_key = self._normalize_key(key)
        path = self._resolve_path(normalized_key)
        if self.auto_mkdir:
            parent = self._parent_path(path)
            if parent:
                await _run_sync_operation(
                    "mkdir",
                    self.operation_timeout_seconds,
                    self.fs.makedirs,
                    parent,
                    exist_ok=True,
                )

        open_kwargs = self._write_open_kwargs(content_type=content_type, metadata=metadata)
        file_obj = await _run_sync_operation(
            "open_writer",
            self.operation_timeout_seconds,
            self.fs.open,
            path,
            "wb",
            **open_kwargs,
        )
        return _AsyncFileWriter(file_obj, self.operation_timeout_seconds)

    @staticmethod
    def _load_storage_options() -> dict[str, Any]:
        raw_options = settings.storage_options_json or "{}"
        try:
            parsed = json.loads(raw_options)
        except json.JSONDecodeError as exc:
            raise KernelError(
                "STORAGE_CONFIG_ERROR",
                "STORAGE_OPTIONS_JSON must be a JSON object",
                {"error": str(exc)},
            ) from exc
        if not isinstance(parsed, dict):
            raise KernelError(
                "STORAGE_CONFIG_ERROR",
                "STORAGE_OPTIONS_JSON must be a JSON object",
            )
        return parsed

    @staticmethod
    def _normalize_storage_options(options: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(options)
        endpoint_url = normalized.pop("endpoint_url", None)
        if endpoint_url:
            client_kwargs = dict(normalized.get("client_kwargs") or {})
            client_kwargs.setdefault("endpoint_url", endpoint_url)
            normalized["client_kwargs"] = client_kwargs
        return normalized

    @staticmethod
    def _normalize_root_path(root_path: str) -> str:
        return root_path.replace("\\", "/").strip("/")

    @staticmethod
    def _normalize_key(key: str) -> str:
        normalized = (key or "").replace("\\", "/").strip()
        if not normalized:
            raise KernelError("STORAGE_INVALID_KEY", "Storage key is required")
        if normalized.startswith("/"):
            raise KernelError(
                "STORAGE_INVALID_KEY",
                "Storage key must be relative",
                {"key": key},
            )

        path = PurePosixPath(normalized)
        if path.is_absolute() or any(part == ".." for part in path.parts):
            raise KernelError(
                "STORAGE_INVALID_KEY",
                "Storage key must not contain absolute or traversal segments",
                {"key": key},
            )
        return path.as_posix()

    def _resolve_path(self, normalized_key: str) -> str:
        if not self.root_path:
            return normalized_key
        return f"{self.root_path.rstrip('/')}/{normalized_key}"

    @staticmethod
    def _parent_path(path: str) -> str:
        parent = PurePosixPath(path).parent.as_posix()
        return "" if parent == "." else parent

    def _is_file(self, path: str) -> bool:
        if not self.fs.exists(path):
            return False
        try:
            return not self.fs.isdir(path)
        except (AttributeError, NotImplementedError):
            return True

    @staticmethod
    def _write_open_kwargs(
        content_type: str | None,
        metadata: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not content_type and not metadata:
            return {}
        return {}
