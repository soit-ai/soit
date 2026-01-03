""" http_tools

HTTP tools port adapter implementation.
"""

from typing import Dict, Any
import httpx

from app.kernel.ports.tools.interface import ToolPort, ToolResponse


class HTTPToolsPort(ToolPort):
    """HTTP tool gateway adapter."""
    
    def __init__(self):
        """Initialize HTTP tool gateway."""
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def invoke(
        self,
        tool_ref: str,
        parameters: Dict[str, Any],
        **kwargs,
    ) -> ToolResponse:
        """Invoke HTTP tool."""
        # Parse tool reference (e.g., "tool:http:create_ticket")
        tool_name = tool_ref.split(":")[-1] if ":" in tool_ref else tool_ref
        
        # Extract HTTP parameters
        url = parameters.get("url")
        method = parameters.get("method", "POST")
        headers = parameters.get("headers", {})
        body = parameters.get("body", {})
        
        if not url:
            return ToolResponse(
                result=None,
                success=False,
                error="Missing URL parameter",
            )
        
        try:
            # Make HTTP request
            if method.upper() == "GET":
                response = await self.client.get(url, headers=headers, params=body)
            elif method.upper() == "POST":
                response = await self.client.post(url, headers=headers, json=body)
            elif method.upper() == "PUT":
                response = await self.client.put(url, headers=headers, json=body)
            elif method.upper() == "DELETE":
                response = await self.client.delete(url, headers=headers)
            else:
                return ToolResponse(
                    result=None,
                    success=False,
                    error=f"Unsupported method: {method}",
                )
            
            response.raise_for_status()
            
            return ToolResponse(
                result=response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text,
                success=True,
                metadata={
                    "http_status": response.status_code,
                    "latency_ms": int(response.elapsed.total_seconds() * 1000),
                },
            )
        except httpx.HTTPError as e:
            return ToolResponse(
                result=None,
                success=False,
                error=str(e),
            )
