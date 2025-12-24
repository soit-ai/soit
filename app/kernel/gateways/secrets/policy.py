""" policy

Secrets gateway policies: audit/access-control.
"""

from typing import Optional
from app.kernel.contracts.context import RequestContext
from app.kernel.gateways.secrets.interface import SecretsGateway
from app.kernel.identity.rbac import require_workspace_write


class SecretsPolicyGateway(SecretsGateway):
    """Secrets gateway with policy enforcement."""
    
    def __init__(
        self,
        gateway: SecretsGateway,
        ctx: RequestContext,
    ):
        """Initialize policy gateway.
        
        Args:
            gateway: Underlying secrets gateway.
            ctx: Request context.
        """
        self.gateway = gateway
        self.ctx = ctx
    
    async def get_secret(
        self,
        secret_ref: str,
        **kwargs: Any,
    ) -> str:
        """Get secret with access control."""
        # Verify workspace write permission (secrets are sensitive)
        require_workspace_write(self.ctx)
        return await self.gateway.get_secret(secret_ref=secret_ref, **kwargs)
    
    async def set_secret(
        self,
        secret_ref: str,
        value: str,
        **kwargs: Any,
    ) -> None:
        """Set secret with access control."""
        require_workspace_write(self.ctx)
        await self.gateway.set_secret(secret_ref=secret_ref, value=value, **kwargs)
    
    async def delete_secret(
        self,
        secret_ref: str,
        **kwargs: Any,
    ) -> None:
        """Delete secret with access control."""
        require_workspace_write(self.ctx)
        await self.gateway.delete_secret(secret_ref=secret_ref, **kwargs)
