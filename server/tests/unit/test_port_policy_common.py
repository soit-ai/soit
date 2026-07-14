"""Unit tests for shared port policy helpers."""

from __future__ import annotations

import asyncio

import pytest

from app.kernel.commons.errors import KernelError, TimeoutError
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.common.policy import (
    error_details,
    resolve_run_id,
    run_with_timeout_retry,
)


def test_resolve_run_id_prefers_kwargs_over_context():
    ctx = RequestContext(tenant_id="t", workspace_id="w", user_id="u")
    object.__setattr__(ctx, "run_id", "run-from-context")

    assert resolve_run_id({"run_id": "run-from-kwargs"}, ctx) == "run-from-kwargs"


def test_error_details_preserves_kernel_error_code_and_details():
    exc = KernelError("CUSTOM", "failed", details={"field": "value"})

    assert error_details(exc) == {"error_type": "KernelError", "code": "CUSTOM", "field": "value"}


@pytest.mark.asyncio
async def test_run_with_timeout_retry_retries_then_succeeds():
    attempts = 0

    async def operation():
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise RuntimeError("transient")
        return "ok"

    result = await run_with_timeout_retry(
        operation,
        timeout_seconds=5,
        max_retries=2,
        timeout_factory=lambda: TimeoutError("timed out"),
        wait_min=0,
        wait_max=0,
    )

    assert result == "ok"
    assert attempts == 2


@pytest.mark.asyncio
async def test_run_with_timeout_retry_raises_kernel_timeout():
    async def operation():
        await asyncio.sleep(0.1)
        return "late"

    with pytest.raises(TimeoutError, match="timed out"):
        await run_with_timeout_retry(
            operation,
            timeout_seconds=0.01,
            max_retries=1,
            timeout_factory=lambda: TimeoutError("timed out"),
            wait_min=0,
            wait_max=0,
        )
