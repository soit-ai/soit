"""Credit guard contract for metered port invocations.

The kernel only knows the contract; the billing module provides the
implementation and the composition root injects it, keeping the kernel
free of module imports.
"""

from __future__ import annotations

from typing import Protocol


class CreditGuard(Protocol):
    """Pre-invocation credit check for a workspace."""

    async def check(self, *, operation: str) -> None:
        """Raise CreditExhaustedError when the workspace may not spend."""
        ...
