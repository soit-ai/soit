""" policy

Storage port policies: timeout/retry/audit/quota.
"""

from typing import Any

from app.kernel.commons.errors import KernelError, TimeoutError
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.common.policy import (
    error_details,
    resolve_run_id,
    run_with_timeout_retry,
    unwrap_retry_error,
)
from app.kernel.ports.storage.interface import (
    StoragePort,
    StorageReader,
    StorageWriter,
    StreamingStoragePort,
)
from app.kernel.runtime.runs.writer import TraceWriter


def _resolve_run_id(kwargs: dict[str, Any], ctx: RequestContext) -> str:
    return resolve_run_id(kwargs, ctx)


def _unwrap_error(exc: Exception) -> Exception:
    return unwrap_retry_error(exc)


def _error_details(exc: Exception) -> dict[str, Any]:
    return error_details(exc)


def _raise_storage_error(code: str, exc: Exception, message: str) -> None:
    if isinstance(exc, KernelError):
        raise
    raise KernelError(code, message, details=_error_details(exc)) from exc

class StoragePolicyGateway(StreamingStoragePort):
    """Storage port with policy enforcement."""

    def __init__(
        self,
        gateway: StoragePort,
        ctx: RequestContext,
        trace_writer: TraceWriter | None = None,
        timeout_seconds: int = 60,
        max_retries: int = 3,
    ):
        """Initialize policy gateway.

        Args:
            gateway: Underlying storage gateway.
            ctx: Request context.
            trace_writer: Optional trace writer.
            timeout_seconds: Request timeout.
            max_retries: Maximum retries.
        """
        self.gateway = gateway
        self.ctx = ctx
        self.trace_writer = trace_writer
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    async def put(
        self,
        key: str,
        data: bytes,
        content_type: str | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> str:
        """Upload object with policy enforcement."""
        step = None
        if self.trace_writer:
            run_id = _resolve_run_id(kwargs, self.ctx)
            if not run_id:
                raise ValueError("run_id is required when trace_writer is enabled")
            step = self.trace_writer.create_step(
                run_id=run_id,
                step_type="io",
                input_summary=f"put key={key}",
            )
            self.trace_writer.update_step_status(step.id, "running")

        start_time = utc_now()
        async def _put():
            return await self.gateway.put(
                key=key,
                data=data,
                content_type=content_type,
                metadata=metadata,
                **kwargs,
            )

        try:
            result_key = await run_with_timeout_retry(
                _put,
                timeout_seconds=self.timeout_seconds,
                max_retries=self.max_retries,
                timeout_factory=lambda: TimeoutError(
                    f"Storage put timed out after {self.timeout_seconds} seconds",
                    {"timeout_seconds": self.timeout_seconds, "key": key}
                ),
                wait_min=2,
                wait_max=10,
            )
        except TimeoutError as exc:
            if step and self.trace_writer:
                self.trace_writer.update_step_status(
                    step.id,
                    "failed",
                    error_code="STORAGE_PUT_ERROR",
                    error_message=str(exc),
                    error_details=_error_details(exc),
                )
            raise
        except Exception as exc:
            if step and self.trace_writer:
                self.trace_writer.update_step_status(
                    step.id,
                    "failed",
                    error_code="STORAGE_PUT_ERROR",
                    error_message=str(_unwrap_error(exc)),
                    error_details=_error_details(exc),
                )
            _raise_storage_error("STORAGE_PUT_ERROR", exc, "Storage put failed")

        # Update cost if trace writer available
        if self.trace_writer and step:
            elapsed_ms = int((utc_now() - start_time).total_seconds() * 1000)
            self.trace_writer.record_cost(
                run_id=_resolve_run_id(kwargs, self.ctx),
                step_id=step.id,
                unit="bytes",
                quantity=len(data),
                provider="storage",
                source_port="storage",
                operation="put",
                latency_ms=elapsed_ms,
                request_count=1,
                storage_bytes=len(data),
            )
            self.trace_writer.update_step_status(
                step.id,
                "succeeded",
                metrics={
                    "storage_bytes": len(data),
                    "latency_ms": elapsed_ms,
                },
            )

        return result_key

    async def get(
        self,
        key: str,
        **kwargs: Any,
    ) -> bytes:
        """Download object with policy enforcement."""
        step = None
        if self.trace_writer:
            run_id = _resolve_run_id(kwargs, self.ctx)
            if not run_id:
                raise ValueError("run_id is required when trace_writer is enabled")
            step = self.trace_writer.create_step(
                run_id=run_id,
                step_type="io",
                input_summary=f"get key={key}",
            )
            self.trace_writer.update_step_status(step.id, "running")

        start_time = utc_now()
        async def _get():
            return await self.gateway.get(key=key, **kwargs)

        try:
            data = await run_with_timeout_retry(
                _get,
                timeout_seconds=self.timeout_seconds,
                max_retries=self.max_retries,
                timeout_factory=lambda: TimeoutError(
                    f"Storage get timed out after {self.timeout_seconds} seconds",
                    {"timeout_seconds": self.timeout_seconds, "key": key}
                ),
                wait_min=2,
                wait_max=10,
            )
            if step and self.trace_writer:
                elapsed_ms = int((utc_now() - start_time).total_seconds() * 1000)
                self.trace_writer.update_step_status(
                    step.id,
                    "succeeded",
                    metrics={
                        "storage_bytes": len(data),
                        "latency_ms": elapsed_ms,
                    },
                )
                self.trace_writer.record_cost(
                    run_id=_resolve_run_id(kwargs, self.ctx),
                    step_id=step.id,
                    unit="bytes",
                    quantity=len(data),
                    provider="storage",
                    source_port="storage",
                    operation="get",
                    latency_ms=elapsed_ms,
                    request_count=1,
                    storage_bytes=len(data),
                )
            return data
        except TimeoutError as exc:
            if step and self.trace_writer:
                self.trace_writer.update_step_status(
                    step.id,
                    "failed",
                    error_code="STORAGE_GET_ERROR",
                    error_message=str(exc),
                    error_details=_error_details(exc),
                )
            raise
        except Exception as exc:
            if step and self.trace_writer:
                self.trace_writer.update_step_status(
                    step.id,
                    "failed",
                    error_code="STORAGE_GET_ERROR",
                    error_message=str(_unwrap_error(exc)),
                    error_details=_error_details(exc),
                )
            _raise_storage_error("STORAGE_GET_ERROR", exc, "Storage get failed")

    async def delete(
        self,
        key: str,
        **kwargs: Any,
    ) -> None:
        """Delete object with policy enforcement."""
        step = None
        if self.trace_writer:
            run_id = _resolve_run_id(kwargs, self.ctx)
            if not run_id:
                raise ValueError("run_id is required when trace_writer is enabled")
            step = self.trace_writer.create_step(
                run_id=run_id,
                step_type="io",
                input_summary=f"delete key={key}",
            )
            self.trace_writer.update_step_status(step.id, "running")

        start_time = utc_now()
        async def _delete():
            return await self.gateway.delete(key=key, **kwargs)

        try:
            await run_with_timeout_retry(
                _delete,
                timeout_seconds=self.timeout_seconds,
                max_retries=self.max_retries,
                timeout_factory=lambda: TimeoutError(
                    f"Storage delete timed out after {self.timeout_seconds} seconds",
                    {"timeout_seconds": self.timeout_seconds, "key": key}
                ),
                wait_min=1,
                wait_max=5,
            )
            if step and self.trace_writer:
                elapsed_ms = int((utc_now() - start_time).total_seconds() * 1000)
                self.trace_writer.update_step_status(
                    step.id,
                    "succeeded",
                    metrics={
                        "latency_ms": elapsed_ms,
                    },
                )
                self.trace_writer.record_cost(
                    run_id=_resolve_run_id(kwargs, self.ctx),
                    step_id=step.id,
                    unit="requests",
                    quantity=1,
                    provider="storage",
                    source_port="storage",
                    operation="delete",
                    latency_ms=elapsed_ms,
                    request_count=1,
                )
        except TimeoutError as exc:
            if step and self.trace_writer:
                self.trace_writer.update_step_status(
                    step.id,
                    "failed",
                    error_code="STORAGE_DELETE_ERROR",
                    error_message=str(exc),
                    error_details=_error_details(exc),
                )
            raise
        except Exception as exc:
            if step and self.trace_writer:
                self.trace_writer.update_step_status(
                    step.id,
                    "failed",
                    error_code="STORAGE_DELETE_ERROR",
                    error_message=str(_unwrap_error(exc)),
                    error_details=_error_details(exc),
                )
            _raise_storage_error("STORAGE_DELETE_ERROR", exc, "Storage delete failed")

    async def exists(
        self,
        key: str,
        **kwargs: Any,
    ) -> bool:
        """Check if object exists."""
        step = None
        if self.trace_writer:
            run_id = _resolve_run_id(kwargs, self.ctx)
            if not run_id:
                raise ValueError("run_id is required when trace_writer is enabled")
            step = self.trace_writer.create_step(
                run_id=run_id,
                step_type="io",
                input_summary=f"exists key={key}",
            )
            self.trace_writer.update_step_status(step.id, "running")

        start_time = utc_now()
        try:
            async def _exists():
                return await self.gateway.exists(key=key, **kwargs)

            result = await run_with_timeout_retry(
                _exists,
                timeout_seconds=self.timeout_seconds,
                max_retries=1,
                timeout_factory=lambda: TimeoutError(
                    f"Storage exists check timed out after {self.timeout_seconds} seconds",
                    {"timeout_seconds": self.timeout_seconds, "key": key}
                ),
            )
            if step and self.trace_writer:
                elapsed_ms = int((utc_now() - start_time).total_seconds() * 1000)
                self.trace_writer.update_step_status(
                    step.id,
                    "succeeded",
                    metrics={
                        "exists": result,
                        "latency_ms": elapsed_ms,
                    },
                )
                self.trace_writer.record_cost(
                    run_id=_resolve_run_id(kwargs, self.ctx),
                    step_id=step.id,
                    unit="requests",
                    quantity=1,
                    provider="storage",
                    source_port="storage",
                    operation="exists",
                    latency_ms=elapsed_ms,
                    request_count=1,
                )
            return result
        except TimeoutError as exc:
            if step and self.trace_writer:
                self.trace_writer.update_step_status(
                    step.id,
                    "failed",
                    error_code="STORAGE_EXISTS_ERROR",
                    error_message=str(exc),
                    error_details=_error_details(exc),
                )
            raise
        except Exception as exc:
            if step and self.trace_writer:
                self.trace_writer.update_step_status(
                    step.id,
                    "failed",
                    error_code="STORAGE_EXISTS_ERROR",
                    error_message=str(_unwrap_error(exc)),
                    error_details=_error_details(exc),
                )
            _raise_storage_error("STORAGE_EXISTS_ERROR", exc, "Storage exists check failed")

    async def open_reader(self, key: str, **kwargs: Any) -> StorageReader:
        """Open a streaming reader with timeout/error policy."""
        open_reader = getattr(self.gateway, "open_reader", None)
        if not open_reader:
            raise KernelError(
                "STORAGE_STREAMING_NOT_SUPPORTED",
                "Storage gateway does not support streaming reads",
                {"key": key},
            )
        try:
            async def _open_reader():
                return await open_reader(key=key, **kwargs)

            return await run_with_timeout_retry(
                _open_reader,
                timeout_seconds=self.timeout_seconds,
                max_retries=1,
                timeout_factory=lambda: TimeoutError(
                    f"Storage open_reader timed out after {self.timeout_seconds} seconds",
                    {"timeout_seconds": self.timeout_seconds, "key": key},
                ),
            )
        except TimeoutError:
            raise
        except Exception as exc:
            _raise_storage_error("STORAGE_OPEN_READER_ERROR", exc, "Storage open_reader failed")

    async def open_writer(
        self,
        key: str,
        content_type: str | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> StorageWriter:
        """Open a streaming writer with timeout/error policy."""
        open_writer = getattr(self.gateway, "open_writer", None)
        if not open_writer:
            raise KernelError(
                "STORAGE_STREAMING_NOT_SUPPORTED",
                "Storage gateway does not support streaming writes",
                {"key": key},
            )
        try:
            async def _open_writer():
                return await open_writer(
                    key=key,
                    content_type=content_type,
                    metadata=metadata,
                    **kwargs,
                )

            return await run_with_timeout_retry(
                _open_writer,
                timeout_seconds=self.timeout_seconds,
                max_retries=1,
                timeout_factory=lambda: TimeoutError(
                    f"Storage open_writer timed out after {self.timeout_seconds} seconds",
                    {"timeout_seconds": self.timeout_seconds, "key": key},
                ),
            )
        except TimeoutError:
            raise
        except Exception as exc:
            _raise_storage_error("STORAGE_OPEN_WRITER_ERROR", exc, "Storage open_writer failed")
