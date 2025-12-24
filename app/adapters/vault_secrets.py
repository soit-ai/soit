""" vault_secrets

Vault secrets gateway adapter implementation.
"""

from typing import Optional
import hvac

from app.kernel.gateways.secrets.interface import SecretsGateway
from app.kernel.config.settings import settings


class VaultSecretsGateway(SecretsGateway):
    """HashiCorp Vault secrets gateway adapter."""
    
    def __init__(
        self,
        url: Optional[str] = None,
        token: Optional[str] = None,
    ):
        """Initialize Vault gateway.
        
        Args:
            url: Vault URL.
            token: Vault token.
        """
        self.url = url or settings.vault_url
        self.token = token or settings.vault_token
        
        if self.url:
            self.client = hvac.Client(url=self.url, token=self.token)
        else:
            self.client = None
    
    async def get_secret(
        self,
        secret_ref: str,
        **kwargs,
    ) -> str:
        """Get secret value."""
        if not self.client:
            raise ValueError("Vault client not initialized")
        
        # Parse secret reference (e.g., "secret:openai_api_key")
        secret_path = secret_ref.split(":")[-1] if ":" in secret_ref else secret_ref
        
        # Read from Vault
        response = self.client.secrets.kv.v2.read_secret_version(path=secret_path)
        data = response["data"]["data"]
        
        # Return first value (or implement proper key extraction)
        return str(list(data.values())[0]) if data else ""
    
    async def set_secret(
        self,
        secret_ref: str,
        value: str,
        **kwargs,
    ) -> None:
        """Set secret value."""
        if not self.client:
            raise ValueError("Vault client not initialized")
        
        secret_path = secret_ref.split(":")[-1] if ":" in secret_ref else secret_ref
        
        # Write to Vault
        self.client.secrets.kv.v2.create_or_update_secret(
            path=secret_path,
            secret={"value": value},
        )
    
    async def delete_secret(
        self,
        secret_ref: str,
        **kwargs,
    ) -> None:
        """Delete secret."""
        if not self.client:
            raise ValueError("Vault client not initialized")
        
        secret_path = secret_ref.split(":")[-1] if ":" in secret_ref else secret_ref
        
        # Delete from Vault
        self.client.secrets.kv.v2.delete_metadata_and_all_versions(path=secret_path)
