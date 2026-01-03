""" vault_secrets

Vault secrets gateway adapter implementation.
"""

from typing import Optional
import hvac

from app.kernel.ports.secrets.interface import SecretsPort
from app.settings.settings import settings


class VaultSecretsPort(SecretsPort):
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
        **kwargs: Any,
    ) -> str:
        """Get secret value.
        
        Args:
            secret_ref: Secret reference (e.g., "secret:openai_api_key").
            **kwargs: Additional parameters.
            
        Returns:
            Secret value (decrypted).
            
        Raises:
            ValueError: If Vault client not initialized.
        """
        if not self.client:
            raise ValueError("Vault client not initialized")
        
        # Parse secret reference (e.g., "secret:openai_api_key")
        # Format: "secret:path/to/secret:key" or "secret:path/to/secret"
        parts = secret_ref.split(":")
        if len(parts) >= 2:
            secret_path = ":".join(parts[1:-1]) if len(parts) > 2 else parts[1]
            secret_key = parts[-1] if len(parts) > 2 else None
        else:
            secret_path = secret_ref
            secret_key = None
        
        try:
            # Read from Vault KV v2
            response = self.client.secrets.kv.v2.read_secret_version(path=secret_path)
            data = response.get("data", {}).get("data", {})
            
            # If key specified, return that value; otherwise return first value
            if secret_key and secret_key in data:
                return str(data[secret_key])
            elif data:
                return str(list(data.values())[0])
            else:
                raise ValueError(f"Secret not found: {secret_ref}")
        except Exception as e:
            raise ValueError(f"Failed to get secret {secret_ref}: {str(e)}")
    
    async def set_secret(
        self,
        secret_ref: str,
        value: str,
        **kwargs: Any,
    ) -> None:
        """Set secret value.
        
        Args:
            secret_ref: Secret reference (e.g., "secret:openai_api_key").
            value: Secret value (will be encrypted).
            **kwargs: Additional parameters.
            
        Raises:
            ValueError: If Vault client not initialized.
        """
        if not self.client:
            raise ValueError("Vault client not initialized")
        
        # Parse secret reference
        parts = secret_ref.split(":")
        if len(parts) >= 2:
            secret_path = ":".join(parts[1:-1]) if len(parts) > 2 else parts[1]
            secret_key = parts[-1] if len(parts) > 2 else "value"
        else:
            secret_path = secret_ref
            secret_key = "value"
        
        try:
            # Write to Vault KV v2
            self.client.secrets.kv.v2.create_or_update_secret(
                path=secret_path,
                secret={secret_key: value},
            )
        except Exception as e:
            raise ValueError(f"Failed to set secret {secret_ref}: {str(e)}")
    
    async def delete_secret(
        self,
        secret_ref: str,
        **kwargs: Any,
    ) -> None:
        """Delete secret.
        
        Args:
            secret_ref: Secret reference (e.g., "secret:openai_api_key").
            **kwargs: Additional parameters.
            
        Raises:
            ValueError: If Vault client not initialized.
        """
        if not self.client:
            raise ValueError("Vault client not initialized")
        
        # Parse secret reference
        parts = secret_ref.split(":")
        if len(parts) >= 2:
            secret_path = ":".join(parts[1:])
        else:
            secret_path = secret_ref
        
        try:
            # Delete from Vault KV v2
            self.client.secrets.kv.v2.delete_metadata_and_all_versions(path=secret_path)
        except Exception as e:
            raise ValueError(f"Failed to delete secret {secret_ref}: {str(e)}")
