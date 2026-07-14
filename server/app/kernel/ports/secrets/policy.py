""" policy

Secrets port policies: audit/access-control.
"""

from typing import Any

from app.kernel.commons.errors import TimeoutError
from app.kernel.contracts.context import RequestContext
from app.kernel.identity.rbac import require_workspace_write_async
from app.kernel.ports.common.policy import run_with_timeout_retry
from app.kernel.ports.secrets.interface import SecretsPort


class SecretsPolicyGateway(SecretsPort):
    """Secrets port with policy enforcement."""

    def __init__(
        self,
        gateway: SecretsPort,
        ctx: RequestContext,
        timeout_seconds: int = 10,
    ):
        """Initialize policy gateway.

        Args:
            gateway: Underlying secrets gateway.
            ctx: Request context.
            timeout_seconds: Request timeout (default 10s for secrets operations).
        """
        self.gateway = gateway
        self.ctx = ctx
        self.timeout_seconds = timeout_seconds

    async def get_secret(
        self,
        secret_ref: str,
        **kwargs: Any,
    ) -> str:
        """Get secret with access control."""
        # Verify workspace write permission (secrets are sensitive)
        await require_workspace_write_async(self.ctx)
        async def _get_secret():
            return await self.gateway.get_secret(secret_ref=secret_ref, **kwargs)

        return await run_with_timeout_retry(
            _get_secret,
            timeout_seconds=self.timeout_seconds,
            max_retries=1,
            timeout_factory=lambda: TimeoutError(
                f"Secrets get timed out after {self.timeout_seconds} seconds",
                {"timeout_seconds": self.timeout_seconds, "secret_ref": secret_ref}
            ),
        )

    async def set_secret(
        self,
        secret_ref: str,
        value: str,
        **kwargs: Any,
    ) -> None:
        """Set secret with access control."""
        await require_workspace_write_async(self.ctx)

        async def _set_secret():
            return await self.gateway.set_secret(secret_ref=secret_ref, value=value, **kwargs)

        await run_with_timeout_retry(
            _set_secret,
            timeout_seconds=self.timeout_seconds,
            max_retries=1,
            timeout_factory=lambda: TimeoutError(
                f"Secrets set timed out after {self.timeout_seconds} seconds",
                {"timeout_seconds": self.timeout_seconds, "secret_ref": secret_ref}
            ),
        )

    async def delete_secret(
        self,
        secret_ref: str,
        **kwargs: Any,
    ) -> None:
        """Delete secret with access control."""
        await require_workspace_write_async(self.ctx)

        async def _delete_secret():
            return await self.gateway.delete_secret(secret_ref=secret_ref, **kwargs)

        await run_with_timeout_retry(
            _delete_secret,
            timeout_seconds=self.timeout_seconds,
            max_retries=1,
            timeout_factory=lambda: TimeoutError(
                f"Secrets delete timed out after {self.timeout_seconds} seconds",
                {"timeout_seconds": self.timeout_seconds, "secret_ref": secret_ref}
            ),
        )
