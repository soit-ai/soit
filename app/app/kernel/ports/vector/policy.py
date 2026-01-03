""" policy

Vector port policies: timeout/retry/rate-limit/audit.
"""

import asyncio
from typing import List, Dict, Any, Optional
from tenacity import retry, stop_after_attempt, wait_exponential

from app.kernel.contracts.context import RequestContext
from app.kernel.ports.vector.interface import VectorPort, VectorQueryResult
from app.kernel.trace.writer import TraceWriter
from app.kernel.commons.time import utc_now
from app.kernel.commons.errors import TimeoutError

def _resolve_run_id(kwargs: Dict[str, Any], ctx: RequestContext) -> str:
    """Resolve run_id for trace emission.

    When trace_writer is enabled, run_id must be present. We allow reading from ctx (best-effort)
    to support propagation via execution context.
    """
    run_id = kwargs.get("run_id") or getattr(ctx, "run_id", None)
    return str(run_id) if run_id else ""

class VectorPolicyGateway(VectorPort):
    """Vector port with policy enforcement."""
    
    def __init__(
        self,
        gateway: VectorPort,
        ctx: RequestContext,
        trace_writer: Optional[TraceWriter] = None,
        timeout_seconds: int = 30,
        max_retries: int = 2,
    ):
        """Initialize policy gateway.
        
        Args:
            gateway: Underlying vector gateway.
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
    
    async def query(
        self,
        collection: str,
        vector: List[float],
        top_k: int = 10,
        filter: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> VectorQueryResult:
        """Query vectors with policy enforcement."""
        step = None
        if self.trace_writer:
            run_id = _resolve_run_id(kwargs, self.ctx)
            if not run_id:
                raise ValueError("run_id is required when trace_writer is enabled")
            step = self.trace_writer.create_step(
                run_id=_resolve_run_id(kwargs, self.ctx),
                step_type="retrieve",
                input_summary=f"collection={collection}, top_k={top_k}",
            )
            self.trace_writer.update_step_status(step.id, "running")
        
        start_time = utc_now()
        try:
            @retry(
                stop=stop_after_attempt(self.max_retries),
                wait=wait_exponential(multiplier=1, min=1, max=5),
            )
            async def _query_with_retry():
                return await self.gateway.query(
                    collection=collection,
                    vector=vector,
                    top_k=top_k,
                    filter=filter,
                    **kwargs,
                )
            
            # Apply timeout
            try:
                result = await asyncio.wait_for(
                    _query_with_retry(),
                    timeout=self.timeout_seconds
                )
            except asyncio.TimeoutError:
                raise TimeoutError(
                    f"Vector query timed out after {self.timeout_seconds} seconds",
                    {"timeout_seconds": self.timeout_seconds, "collection": collection}
                )
            
            if step and self.trace_writer:
                elapsed_ms = int((utc_now() - start_time).total_seconds() * 1000)
                self.trace_writer.update_step_status(
                    step.id,
                    "succeeded",
                    metrics={
                        "vector_count": len(result.ids),
                        "top_k": top_k,
                        "latency_ms": elapsed_ms,
                    },
                )
            
            return result
        except Exception as e:
            if step and self.trace_writer:
                self.trace_writer.update_step_status(
                    step.id,
                    "failed",
                    error_code="VECTOR_QUERY_ERROR",
                    error_message=str(e),
                )
            raise
    
    async def insert(
        self,
        collection: str,
        vectors: List[List[float]],
        ids: List[str],
        metadata: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> None:
        """Insert vectors with policy enforcement."""
        @retry(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=1, min=1, max=5),
        )
        async def _insert_with_retry():
            return await self.gateway.insert(
                collection=collection,
                vectors=vectors,
                ids=ids,
                metadata=metadata,
                **kwargs,
            )
        
        # Apply timeout
        try:
            await asyncio.wait_for(
                _insert_with_retry(),
                timeout=self.timeout_seconds
            )
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"Vector insert timed out after {self.timeout_seconds} seconds",
                {"timeout_seconds": self.timeout_seconds, "collection": collection}
            )
    
    async def delete(
        self,
        collection: str,
        ids: List[str],
        **kwargs: Any,
    ) -> None:
        """Delete vectors with policy enforcement."""
        @retry(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=1, min=1, max=5),
        )
        async def _delete_with_retry():
            return await self.gateway.delete(
                collection=collection,
                ids=ids,
                **kwargs,
            )
        
        # Apply timeout
        try:
            await asyncio.wait_for(
                _delete_with_retry(),
                timeout=self.timeout_seconds
            )
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"Vector delete timed out after {self.timeout_seconds} seconds",
                {"timeout_seconds": self.timeout_seconds, "collection": collection}
            )
