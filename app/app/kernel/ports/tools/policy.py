""" policy

Tool port policies: timeout/retry/rate-limit/audit/egress.
"""

import asyncio
from typing import Dict, Any, Optional
from tenacity import retry, stop_after_attempt, wait_exponential

from app.kernel.contracts.context import RequestContext
from app.kernel.ports.tools.interface import ToolPort, ToolResponse
from app.kernel.ports.common.audit import log_gateway_request
from app.kernel.trace.writer import TraceWriter
from app.kernel.commons.time import utc_now
from app.kernel.commons.errors import TimeoutError
from app.kernel.security.egress import check_egress_policy

def _resolve_run_id(kwargs: Dict[str, Any], ctx: RequestContext) -> str:
    """Resolve run_id for trace emission.

    When trace_writer is enabled, run_id must be present. We allow reading from ctx (best-effort)
    to support propagation via execution context.
    """
    run_id = kwargs.get("run_id") or getattr(ctx, "run_id", None)
    return str(run_id) if run_id else ""

class ToolPolicyGateway(ToolPort):
    """Tool port with policy enforcement."""
    
    def __init__(
        self,
        gateway: ToolPort,
        ctx: RequestContext,
        trace_writer: Optional[TraceWriter] = None,
        timeout_seconds: int = 30,
        max_retries: int = 2,
        enable_egress_check: bool = True,
    ):
        """Initialize policy gateway.
        
        Args:
            gateway: Underlying tool gateway.
            ctx: Request context.
            trace_writer: Optional trace writer.
            timeout_seconds: Request timeout.
            max_retries: Maximum retries.
            enable_egress_check: Enable egress policy check.
        """
        self.gateway = gateway
        self.ctx = ctx
        self.trace_writer = trace_writer
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.enable_egress_check = enable_egress_check
    
    async def invoke(
        self,
        tool_ref: str,
        parameters: Dict[str, Any],
        **kwargs: Any,
    ) -> ToolResponse:
        """Invoke tool with policy enforcement.
        
        Args:
            tool_ref: Tool reference.
            parameters: Tool parameters.
            **kwargs: Additional parameters.
            
        Returns:
            ToolResponse instance.
        """
        # Egress policy check
        if self.enable_egress_check:
            check_egress_policy(self.ctx, tool_ref, parameters)
        
        step = None
        if self.trace_writer:
            run_id = _resolve_run_id(kwargs, self.ctx)
            if not run_id:
                raise ValueError("run_id is required when trace_writer is enabled")
            step = self.trace_writer.create_step(
                run_id=_resolve_run_id(kwargs, self.ctx),
                step_type="tool",
                input_summary=f"tool={tool_ref}",
            )
            self.trace_writer.update_step_status(step.id, "running")
        
        start_time = utc_now()
        try:
            @retry(
                stop=stop_after_attempt(self.max_retries),
                wait=wait_exponential(multiplier=1, min=1, max=5),
            )
            async def _invoke_with_retry():
                return await self.gateway.invoke(
                    tool_ref=tool_ref,
                    parameters=parameters,
                    **kwargs,
                )
            
            # Apply timeout
            try:
                response = await asyncio.wait_for(
                    _invoke_with_retry(),
                    timeout=self.timeout_seconds
                )
            except asyncio.TimeoutError:
                raise TimeoutError(
                    f"Tool invocation timed out after {self.timeout_seconds} seconds",
                    {"timeout_seconds": self.timeout_seconds, "tool_ref": tool_ref}
                )
            
            # Audit log
            if step and self.trace_writer:
                await log_gateway_request(
                    trace_writer=self.trace_writer,
                    run_id=_resolve_run_id(kwargs, self.ctx),
                    step_id=step.id,
                    gateway_type="tool",
                    request_data={
                        "tool_ref": tool_ref,
                        "parameters": parameters,
                    },
                    response_data={
                        "success": response.success,
                        "result_type": type(response.result).__name__ if response.result else None,
                        "metadata": response.metadata,
                        "error": response.error,
                    },
                )
            
            if step and self.trace_writer:
                elapsed_ms = int((utc_now() - start_time).total_seconds() * 1000)
                metrics = {
                    "latency_ms": elapsed_ms,
                    "success": response.success,
                    **response.metadata,
                }
                self.trace_writer.update_step_status(
                    step.id,
                    "succeeded" if response.success else "failed",
                    output_summary=str(response.result)[:100] if response.result else None,
                    metrics=metrics,
                    error_code=None if response.success else "TOOL_ERROR",
                    error_message=response.error,
                )
            
            return response
        except Exception as e:
            if step and self.trace_writer:
                self.trace_writer.update_step_status(
                    step.id,
                    "failed",
                    error_code="TOOL_ERROR",
                    error_message=str(e),
                )
            raise
