"""Credit guard contract for metered port invocations.

The kernel only knows the contract; the billing module provides the
implementation and the composition root injects it, keeping the kernel
free of module imports.
"""

from __future__ import annotations

import inspect
from functools import lru_cache
from typing import Protocol


class CreditGuard(Protocol):
    """Pre-invocation credit check for a workspace."""

    async def check(self, *, operation: str, run_id: str | None = None) -> None:
        """Raise when the workspace may not spend on this call.

        `run_id` names the run the call belongs to, so a guard can apply
        limits kept for what the run executes, such as an agent's budget.
        """
        ...


@lru_cache(maxsize=64)
def _accepts_run_id(guard_type: type) -> bool:
    try:
        parameters = inspect.signature(guard_type.check).parameters
    except (TypeError, ValueError):
        return False
    return "run_id" in parameters or any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in parameters.values()
    )


async def check_spend(guard: CreditGuard, *, operation: str, run_id: str | None = None) -> None:
    """Ask ``guard`` whether this call may spend.

    Guards written before ``run_id`` existed take only ``operation``; they are
    still called, without it, so an older extension keeps working.
    """
    if _accepts_run_id(type(guard)):
        await guard.check(operation=operation, run_id=run_id)
    else:
        await guard.check(operation=operation)  # type: ignore[call-arg]


async def check_unpriced(
    guard: CreditGuard | None,
    *,
    operation: str,
    run_id: str | None,
    ref: str,
    reason: str,
) -> None:
    """Ask ``guard`` whether a call no price applies to may go ahead.

    ``ref`` is the model or tool the call would reach and ``reason`` why it
    has no price (``pricing_not_configured``, ``image_variant_not_priced``...).
    A guard without ``check_unpriced`` allows it, as every call was before.
    """
    handler = getattr(guard, "check_unpriced", None)
    if handler is None:
        return
    await handler(operation=operation, run_id=run_id, ref=ref, reason=reason)
