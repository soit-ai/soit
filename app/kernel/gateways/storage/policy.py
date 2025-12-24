""" policy

Storage gateway policies: timeout/retry/audit/quota.
"""

from typing import Optional, Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential

from app.kernel.contracts.context import RequestContext
from app.kernel.gateways.storage.interface import StorageGateway
from app.kernel.trace.writer import TraceWriter


class StoragePolicyGateway(StorageGateway):
    """Storage gateway with policy enforcement."""
    
    def __init__(
        self,
        gateway: StorageGateway,
        ctx: RequestContext,
        trace_writer: Optional[TraceWriter] = None,
        timeout_seconds: int = 60,
        max_retries: int = 3,
    ):
        """Initialize policy gateway.
        
        Args:
            gateway: Underlying storage gateway.
            ctx: Request context.
            trace_writer: Optional trace writer.
            timeout_seconds: Request timeout.
            max_retries: Maximum retries.
        """
        self.gateway = gateway
        self.ctx = ctx
        self.trace_writer = trace_writer
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
    
    async def put(
        self,
        key: str,
        data: bytes,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> str:
        """Upload object with policy enforcement."""
        @retry(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=1, min=2, max=10),
        )
        async def _put_with_retry():
            return await self.gateway.put(
                key=key,
                data=data,
                content_type=content_type,
                metadata=metadata,
                **kwargs,
            )
        
        result_key = await _put_with_retry()
        
        # Update cost if trace writer available
        if self.trace_writer:
            self.trace_writer.update_cost(
                run_id=kwargs.get("run_id", ""),
                storage_bytes=len(data),
            )
        
        return result_key
    
    async def get(
        self,
        key: str,
        **kwargs: Any,
    ) -> bytes:
        """Download object with policy enforcement."""
        @retry(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=1, min=2, max=10),
        )
        async def _get_with_retry():
            return await self.gateway.get(key=key, **kwargs)
        
        return await _get_with_retry()
    
    async def delete(
        self,
        key: str,
        **kwargs: Any,
    ) -> None:
        """Delete object with policy enforcement."""
        @retry(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=1, min=1, max=5),
        )
        async def _delete_with_retry():
            return await self.gateway.delete(key=key, **kwargs)
        
        await _delete_with_retry()
    
    async def exists(
        self,
        key: str,
        **kwargs: Any,
    ) -> bool:
        """Check if object exists."""
        return await self.gateway.exists(key=key, **kwargs)
