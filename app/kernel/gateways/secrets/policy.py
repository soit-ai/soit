""" policy

Secrets gateway policies: audit/access-control.
"""

import asyncio
from typing import Optional, Any
from app.kernel.contracts.context import RequestContext
from app.kernel.gateways.secrets.interface import SecretsGateway
from app.kernel.identity.rbac import require_workspace_write
from app.kernel.commons.errors import TimeoutError


class SecretsPolicyGateway(SecretsGateway):
    """Secrets gateway with policy enforcement."""
    
    def __init__(
        self,
        gateway: SecretsGateway,
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
        require_workspace_write(self.ctx)
        # Apply timeout
        try:
            return await asyncio.wait_for(
                self.gateway.get_secret(secret_ref=secret_ref, **kwargs),
                timeout=self.timeout_seconds
            )
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"Secrets get timed out after {self.timeout_seconds} seconds",
                {"timeout_seconds": self.timeout_seconds, "secret_ref": secret_ref}
            )
    
    async def set_secret(
        self,
        secret_ref: str,
        value: str,
        **kwargs: Any,
    ) -> None:
        """Set secret with access control."""
        require_workspace_write(self.ctx)
        # Apply timeout
        try:
            await asyncio.wait_for(
                self.gateway.set_secret(secret_ref=secret_ref, value=value, **kwargs),
                timeout=self.timeout_seconds
            )
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"Secrets set timed out after {self.timeout_seconds} seconds",
                {"timeout_seconds": self.timeout_seconds, "secret_ref": secret_ref}
            )
    
    async def delete_secret(
        self,
        secret_ref: str,
        **kwargs: Any,
    ) -> None:
        """Delete secret with access control."""
        require_workspace_write(self.ctx)
        # Apply timeout
        try:
            await asyncio.wait_for(
                self.gateway.delete_secret(secret_ref=secret_ref, **kwargs),
                timeout=self.timeout_seconds
            )
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"Secrets delete timed out after {self.timeout_seconds} seconds",
                {"timeout_seconds": self.timeout_seconds, "secret_ref": secret_ref}
            )
