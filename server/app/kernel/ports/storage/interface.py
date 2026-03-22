""" interface

Object storage port interface.
"""

from typing import Optional, Dict, Any
from abc import ABC, abstractmethod


class StoragePort(ABC):
    """Object storage port interface."""
    
    @abstractmethod
    async def put(
        self,
        key: str,
        data: bytes,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> str:
        """Upload object.
        
        Args:
            key: Storage key (path).
            data: Object data.
            content_type: Optional content type.
            metadata: Optional metadata.
            **kwargs: Additional parameters.
            
        Returns:
            Storage key (same as input or modified).
        """
        pass
    
    @abstractmethod
    async def get(
        self,
        key: str,
        **kwargs: Any,
    ) -> bytes:
        """Download object.
        
        Args:
            key: Storage key.
            **kwargs: Additional parameters.
            
        Returns:
            Object data.
        """
        pass
    
    @abstractmethod
    async def delete(
        self,
        key: str,
        **kwargs: Any,
    ) -> None:
        """Delete object.
        
        Args:
            key: Storage key.
            **kwargs: Additional parameters.
        """
        pass
    
    @abstractmethod
    async def exists(
        self,
        key: str,
        **kwargs: Any,
    ) -> bool:
        """Check if object exists.
        
        Args:
            key: Storage key.
            **kwargs: Additional parameters.
            
        Returns:
            True if exists.
        """
        pass
