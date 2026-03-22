""" interface

Tool port interface.
"""

from typing import Dict, Any, Optional
from abc import ABC, abstractmethod


class ToolResponse:
    """Tool execution response."""
    
    def __init__(
        self,
        result: Any,
        success: bool = True,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Initialize tool response.
        
        Args:
            result: Tool execution result.
            success: Whether execution succeeded.
            error: Error message if failed.
            metadata: Optional metadata (latency, http_status, etc.).
        """
        self.result = result
        self.success = success
        self.error = error
        self.metadata = metadata or {}


class ToolPort(ABC):
    """Tool port interface."""
    
    @abstractmethod
    async def invoke(
        self,
        tool_ref: str,
        parameters: Dict[str, Any],
        **kwargs: Any,
    ) -> ToolResponse:
        """Invoke a tool.
        
        Args:
            tool_ref: Tool reference (e.g., "tool:http:create_ticket").
            parameters: Tool parameters.
            **kwargs: Additional parameters (run_id, etc.).
            
        Returns:
            ToolResponse instance.
        """
        pass
