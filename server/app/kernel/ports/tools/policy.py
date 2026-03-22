""" policy

Tool port policies: timeout/retry/rate-limit/audit/egress.
"""

import asyncio
from typing import Dict, Any, Optional, Tuple
from tenacity import retry, stop_after_attempt, wait_exponential

from app.kernel.contracts.context import RequestContext
from app.kernel.ports.tools.interface import ToolPort, ToolResponse
from app.kernel.ports.storage.interface import StoragePort
from app.kernel.ports.secrets.interface import SecretsPort
from app.kernel.ports.common.audit import log_gateway_request
from app.kernel.ports.common.rate_limiter import RateLimiter
from app.kernel.trace.writer import TraceWriter
from app.kernel.commons.time import utc_now
from app.kernel.commons.errors import TimeoutError, KernelError, ValidationError
from app.kernel.security.egress import check_egress_policy

def _resolve_run_id(kwargs: Dict[str, Any], ctx: RequestContext) -> str:
    """Resolve run_id for trace emission.

    When trace_writer is enabled, run_id must be present. We allow reading from ctx (best-effort)
    to support propagation via execution context.
    """
    run_id = kwargs.get("run_id") or getattr(ctx, "run_id", None)
    return str(run_id) if run_id else ""


def _error_details(exc: Exception) -> Dict[str, Any]:
    details: Dict[str, Any] = {"error_type": type(exc).__name__}
    if isinstance(exc, KernelError):
        details["code"] = exc.code
        details.update(exc.details or {})
    else:
        details["detail"] = str(exc)
    return details


def _provider_from_tool_ref(tool_ref: str) -> Optional[str]:
    if not tool_ref:
        return None
    if tool_ref.startswith("tool:"):
        parts = tool_ref.split(":")
        if len(parts) >= 2:
            return parts[1]
    return None

class ToolPolicyGateway(ToolPort):
    """Tool port with policy enforcement."""
    
    def __init__(
        self,
        gateway: ToolPort,
        ctx: RequestContext,
        trace_writer: Optional[TraceWriter] = None,
        storage_port: Optional[StoragePort] = None,
        secrets_port: Optional[SecretsPort] = None,
        timeout_seconds: int = 30,
        max_retries: int = 2,
        enable_egress_check: bool = True,
        rate_limit_per_minute: Optional[int] = None,
        daily_quota: Optional[int] = None,
        rate_limiter: Optional[RateLimiter] = None,
    ):
        """Initialize policy gateway.
        
        Args:
            gateway: Underlying tool gateway.
            ctx: Request context.
            trace_writer: Optional trace writer.
            timeout_seconds: Request timeout.
            max_retries: Maximum retries.
            enable_egress_check: Enable egress policy check.
            rate_limit_per_minute: Optional rate limit per minute.
            daily_quota: Optional daily request quota.
            rate_limiter: Optional rate limiter instance.
        """
        self.gateway = gateway
        self.ctx = ctx
        self.trace_writer = trace_writer
        self.storage_port = storage_port
        self.secrets_port = secrets_port
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.enable_egress_check = enable_egress_check
        self.rate_limit_per_minute = rate_limit_per_minute
        self.daily_quota = daily_quota
        self.rate_limiter = rate_limiter or RateLimiter()

    def _contains_secret_ref(self, value: Any) -> bool:
        if isinstance(value, dict):
            if "secret_ref" in value:
                return True
            return any(self._contains_secret_ref(item) for item in value.values())
        if isinstance(value, list):
            return any(self._contains_secret_ref(item) for item in value)
        return False

    def _redacted_secret_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Build redacted payload for secret references."""
        redacted = {}
        secret_ref = payload.get("secret_ref")
        if secret_ref:
            redacted["secret_ref"] = secret_ref
        signing_policy_ref = payload.get("signing_policy_ref")
        if signing_policy_ref:
            redacted["signing_policy_ref"] = signing_policy_ref
        return redacted

    async def _resolve_secrets(self, value: Any) -> Tuple[Any, Any]:
        if isinstance(value, dict):
            if "secret_ref" in value:
                secret_ref = value.get("secret_ref")
                if not secret_ref:
                    raise ValidationError("secret_ref is required for secret injection")
                if not self.secrets_port:
                    raise ValidationError("Secrets port not configured for secret injection")
                secret_value = await self.secrets_port.get_secret(secret_ref=secret_ref)
                return secret_value, self._redacted_secret_payload(value)
            resolved: Dict[str, Any] = {}
            redacted: Dict[str, Any] = {}
            for key, item in value.items():
                resolved_value, redacted_value = await self._resolve_secrets(item)
                resolved[key] = resolved_value
                redacted[key] = redacted_value
            return resolved, redacted
        if isinstance(value, list):
            resolved_list = []
            redacted_list = []
            for item in value:
                resolved_item, redacted_item = await self._resolve_secrets(item)
                resolved_list.append(resolved_item)
                redacted_list.append(redacted_item)
            return resolved_list, redacted_list
        return value, value
    
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
        step = None
        redacted_parameters = parameters
        resolved_parameters = parameters
        if self._contains_secret_ref(parameters):
            if not self.secrets_port:
                raise ValidationError("Secrets port not configured for secret injection")
            resolved_parameters, redacted_parameters = await self._resolve_secrets(parameters)
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
            # Egress policy check
            if self.enable_egress_check:
                check_egress_policy(self.ctx, tool_ref, resolved_parameters)

            rate_limit = kwargs.get("rate_limit_per_minute") or self.rate_limit_per_minute
            if rate_limit:
                rate_limit_key = f"tool:{tool_ref}:{self.ctx.tenant_id}:{self.ctx.workspace_id}:{self.ctx.user_id}"
                await self.rate_limiter.check_rate_limit(
                    key=rate_limit_key,
                    limit=rate_limit,
                    window_seconds=60,
                )
            if self.daily_quota:
                quota_key = f"quota:tool:{tool_ref}:{self.ctx.tenant_id}:{self.ctx.workspace_id}"
                await self.rate_limiter.check_rate_limit(
                    key=quota_key,
                    limit=self.daily_quota,
                    window_seconds=86400,
                )

            @retry(
                stop=stop_after_attempt(self.max_retries),
                wait=wait_exponential(multiplier=1, min=1, max=5),
            )
            async def _invoke_with_retry():
                return await self.gateway.invoke(
                    tool_ref=tool_ref,
                    parameters=resolved_parameters,
                    **kwargs,
                )
            
            # Apply timeout
            timeout_seconds = kwargs.get("timeout_s") or self.timeout_seconds
            try:
                response = await asyncio.wait_for(
                    _invoke_with_retry(),
                    timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                raise TimeoutError(
                    f"Tool invocation timed out after {timeout_seconds} seconds",
                    {"timeout_seconds": timeout_seconds, "tool_ref": tool_ref}
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
                        "parameters": redacted_parameters,
                    },
                    response_data={
                        "success": response.success,
                        "result_type": type(response.result).__name__ if response.result else None,
                        "metadata": response.metadata,
                        "error": response.error,
                    },
                    storage_port=self.storage_port,
                )
            
            if step and self.trace_writer:
                elapsed_ms = int((utc_now() - start_time).total_seconds() * 1000)
                metrics = {
                    "latency_ms": elapsed_ms,
                    "success": response.success,
                    "tool_ref": tool_ref,
                    **response.metadata,
                }
                error_details = None
                if not response.success:
                    error_details = {
                        "error_type": "ToolResponseError",
                        "detail": response.error,
                    }
                self.trace_writer.update_step_status(
                    step.id,
                    "succeeded" if response.success else "failed",
                    output_summary=str(response.result)[:100] if response.result else None,
                    metrics=metrics,
                    error_code=None if response.success else "TOOL_ERROR",
                    error_message=response.error,
                    error_details=error_details,
                )
                self.trace_writer.record_cost(
                    run_id=_resolve_run_id(kwargs, self.ctx),
                    step_id=step.id,
                    unit="requests",
                    quantity=1,
                    provider=_provider_from_tool_ref(tool_ref),
                    tool_ref=tool_ref,
                )
            
            return response
        except Exception as e:
            if step and self.trace_writer:
                self.trace_writer.update_step_status(
                    step.id,
                    "failed",
                    error_code="TOOL_ERROR",
                    error_message=str(e),
                    error_details=_error_details(e),
                )
            raise
