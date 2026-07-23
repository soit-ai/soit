"""Runtime secret resolution policy."""

from typing import Any

from app.kernel.commons.errors import TimeoutError
from app.kernel.contracts.context import RequestContext
from app.kernel.identity.rbac import require_workspace_read_async
from app.kernel.ports.common.policy import run_with_timeout_retry
from app.kernel.ports.secrets.interface import SecretsPort


class SecretsPolicyGateway(SecretsPort):
    """Apply user authorization and timeouts to scoped secret resolution."""

    def __init__(
        self,
        gateway: SecretsPort,
        ctx: RequestContext,
        timeout_seconds: int = 10,
    ) -> None:
        self.gateway = gateway
        self.ctx = ctx
        self.timeout_seconds = timeout_seconds

    async def get_secret(self, secret_id: str, **kwargs: Any) -> str:
        """Resolve an opaque secret ID for a workspace reader."""
        await require_workspace_read_async(self.ctx)

        async def _get_secret() -> str:
            return await self.gateway.get_secret(secret_id=secret_id, **kwargs)

        return await run_with_timeout_retry(
            _get_secret,
            timeout_seconds=self.timeout_seconds,
            max_retries=1,
            timeout_factory=lambda: TimeoutError(
                f"Secrets get timed out after {self.timeout_seconds} seconds",
                {"timeout_seconds": self.timeout_seconds, "secret_id": secret_id},
            ),
        )
