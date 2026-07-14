"""Shared helpers for kernel port policy gateways."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from tenacity import RetryError, retry, stop_after_attempt, wait_exponential

from app.kernel.commons.errors import KernelError
from app.kernel.contracts.context import RequestContext

T = TypeVar("T")


def resolve_run_id(kwargs: dict[str, Any], ctx: RequestContext) -> str:
    """Resolve run_id for trace emission."""

    run_id = kwargs.get("run_id") or getattr(ctx, "run_id", None)
    return str(run_id) if run_id else ""


def error_details(exc: Exception) -> dict[str, Any]:
    """Build stable trace error details for gateway failures."""

    root_exc = unwrap_retry_error(exc)
    details: dict[str, Any] = {"error_type": type(root_exc).__name__}
    if isinstance(root_exc, KernelError):
        details["code"] = root_exc.code
        details.update(root_exc.details or {})
    else:
        details["detail"] = str(root_exc)
    if root_exc is not exc:
        details["retry_error"] = str(exc)
    return details


def unwrap_retry_error(exc: Exception) -> Exception:
    """Return the last underlying exception for tenacity RetryError."""

    if isinstance(exc, RetryError):
        try:
            last_exc = exc.last_attempt.exception()
        except Exception:
            last_exc = None
        if last_exc:
            return last_exc
    return exc


async def run_with_timeout_retry(
    operation: Callable[[], Awaitable[T]],
    *,
    timeout_seconds: float,
    max_retries: int,
    timeout_factory: Callable[[], Exception],
    wait_multiplier: float = 1,
    wait_min: float = 1,
    wait_max: float = 10,
) -> T:
    """Run an async operation with the same retry-then-timeout shape used by port policies."""

    @retry(
        stop=stop_after_attempt(max_retries),
        wait=wait_exponential(multiplier=wait_multiplier, min=wait_min, max=wait_max),
    )
    async def _with_retry() -> T:
        return await operation()

    try:
        return await asyncio.wait_for(_with_retry(), timeout=timeout_seconds)
    except TimeoutError:
        raise timeout_factory()


__all__ = ["resolve_run_id", "error_details", "run_with_timeout_retry", "unwrap_retry_error"]
