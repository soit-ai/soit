""" policy

Storage port policies: timeout/retry/audit/quota.
"""

import asyncio
from typing import Optional, Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential, RetryError

from app.kernel.contracts.context import RequestContext
from app.kernel.ports.storage.interface import StoragePort
from app.kernel.trace.writer import TraceWriter
from app.kernel.commons.time import utc_now
from app.kernel.commons.errors import TimeoutError, KernelError

def _resolve_run_id(kwargs: Dict[str, Any], ctx: RequestContext) -> str:
    """Resolve run_id for trace emission.

    When trace_writer is enabled, run_id must be present. We allow reading from ctx (best-effort)
    to support propagation via execution context.
    """
    run_id = kwargs.get("run_id") or getattr(ctx, "run_id", None)
    return str(run_id) if run_id else ""


def _unwrap_error(exc: Exception) -> Exception:
    if isinstance(exc, RetryError):
        try:
            last_exc = exc.last_attempt.exception()
        except Exception:
            last_exc = None
        if last_exc:
            return last_exc
    return exc


def _error_details(exc: Exception) -> Dict[str, Any]:
    root_exc = _unwrap_error(exc)
    details: Dict[str, Any] = {"error_type": type(root_exc).__name__}
    if isinstance(root_exc, KernelError):
        details["code"] = root_exc.code
        details.update(root_exc.details or {})
    else:
        details["detail"] = str(root_exc)
    if root_exc is not exc:
        details["retry_error"] = str(exc)
    return details


def _raise_storage_error(code: str, exc: Exception, message: str) -> None:
    if isinstance(exc, KernelError):
        raise
    raise KernelError(code, message, details=_error_details(exc)) from exc

class StoragePolicyGateway(StoragePort):
    """Storage port with policy enforcement."""
    
    def __init__(
        self,
        gateway: StoragePort,
        ctx: RequestContext,
        trace_writer: Optional[TraceWriter] = None,
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
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
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
        @retry(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=1, min=2, max=10),
        )
        async def _put_with_retry():
            return await self.gateway.put(
                key=key,
                data=data,
                content_type=content_type,
                metadata=metadata,
                **kwargs,
            )
        
        # Apply timeout
        try:
            result_key = await asyncio.wait_for(
                _put_with_retry(),
                timeout=self.timeout_seconds
            )
        except asyncio.TimeoutError:
            exc = TimeoutError(
                f"Storage put timed out after {self.timeout_seconds} seconds",
                {"timeout_seconds": self.timeout_seconds, "key": key}
            )
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
            self.trace_writer.record_cost(
                run_id=_resolve_run_id(kwargs, self.ctx),
                step_id=step.id,
                unit="bytes",
                quantity=len(data),
                provider="storage",
            )
            elapsed_ms = int((utc_now() - start_time).total_seconds() * 1000)
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
        @retry(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=1, min=2, max=10),
        )
        async def _get_with_retry():
            return await self.gateway.get(key=key, **kwargs)
        
        # Apply timeout
        try:
            data = await asyncio.wait_for(
                _get_with_retry(),
                timeout=self.timeout_seconds
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
                )
            return data
        except asyncio.TimeoutError:
            exc = TimeoutError(
                f"Storage get timed out after {self.timeout_seconds} seconds",
                {"timeout_seconds": self.timeout_seconds, "key": key}
            )
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
        @retry(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=1, min=1, max=5),
        )
        async def _delete_with_retry():
            return await self.gateway.delete(key=key, **kwargs)
        
        # Apply timeout
        try:
            await asyncio.wait_for(
                _delete_with_retry(),
                timeout=self.timeout_seconds
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
                )
        except asyncio.TimeoutError:
            exc = TimeoutError(
                f"Storage delete timed out after {self.timeout_seconds} seconds",
                {"timeout_seconds": self.timeout_seconds, "key": key}
            )
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
        # Apply timeout
        try:
            result = await asyncio.wait_for(
                self.gateway.exists(key=key, **kwargs),
                timeout=self.timeout_seconds
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
                )
            return result
        except asyncio.TimeoutError:
            exc = TimeoutError(
                f"Storage exists check timed out after {self.timeout_seconds} seconds",
                {"timeout_seconds": self.timeout_seconds, "key": key}
            )
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
