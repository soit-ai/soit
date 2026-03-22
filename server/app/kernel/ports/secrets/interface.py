""" interface

Secrets port interface.
"""

from typing import Optional, Any
from abc import ABC, abstractmethod


class SecretsPort(ABC):
    """Secrets port interface."""
    
    @abstractmethod
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
        """
        pass
    
    @abstractmethod
    async def set_secret(
        self,
        secret_ref: str,
        value: str,
        **kwargs: Any,
    ) -> None:
        """Set secret value.
        
        Args:
            secret_ref: Secret reference.
            value: Secret value (will be encrypted).
            **kwargs: Additional parameters.
        """
        pass
    
    @abstractmethod
    async def delete_secret(
        self,
        secret_ref: str,
        **kwargs: Any,
    ) -> None:
        """Delete secret.
        
        Args:
            secret_ref: Secret reference.
            **kwargs: Additional parameters.
        """
        pass
