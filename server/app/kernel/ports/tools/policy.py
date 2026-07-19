""" policy

Tool port policies: timeout/retry/rate-limit/audit/egress.
"""

import math
from typing import Any

from opentelemetry import trace
from opentelemetry.trace import Tracer

from app.kernel.commons.errors import TimeoutError, ValidationError
from app.kernel.commons.ids import generate_ulid
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.contracts.tool_call import (
    ToolCallError,
    ToolCallRequest,
    ToolCallResult,
)
from app.kernel.ports.common.audit import log_gateway_request
from app.kernel.ports.common.policy import (
    error_details,
    resolve_run_id,
    run_with_timeout_retry,
)
from app.kernel.ports.common.rate_limiter import RateLimiter
from app.kernel.ports.secrets.interface import SecretsPort
from app.kernel.ports.storage.interface import StoragePort
from app.kernel.ports.tools.interface import ToolPort, ToolResponse
from app.kernel.runtime.runs.tool_calls import (
    RuntimeToolExecutionService,
    ToolExecutionCommand,
    summarize_parameters,
    summarize_tool_payload,
)
from app.kernel.runtime.runs.writer import TraceWriter
from app.kernel.security.egress import check_egress_policy


def _provider_from_tool_ref(tool_ref: str) -> str | None:
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
        trace_writer: TraceWriter | None = None,
        storage_port: StoragePort | None = None,
        secrets_port: SecretsPort | None = None,
        timeout_seconds: int = 30,
        max_retries: int = 2,
        enable_egress_check: bool = True,
        rate_limit_per_minute: int | None = None,
        daily_quota: int | None = None,
        rate_limiter: RateLimiter | None = None,
        otel_tracer: Tracer | None = None,
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
        self.otel_tracer = otel_tracer or trace.get_tracer("soit.tools")

    def register_builtin(self, tool_ref: str, ctx: RequestContext) -> bool:
        """Register a built-in tool through the wrapped gateway when supported."""
        register = getattr(self.gateway, "register_builtin", None)
        if register is None:
            return False
        return bool(register(tool_ref, ctx))

    def get_tool_policy(
        self,
        tool_ref: str,
        ctx: RequestContext,
    ) -> dict[str, Any]:
        """Return ToolSpec policy through the wrapped gateway when supported."""

        get_policy = getattr(self.gateway, "get_tool_policy", None)
        if get_policy is None:
            return {}
        return dict(get_policy(tool_ref, ctx) or {})

    def _contains_secret_ref(self, value: Any) -> bool:
        if isinstance(value, dict):
            if "secret_ref" in value:
                return True
            return any(self._contains_secret_ref(item) for item in value.values())
        if isinstance(value, list):
            return any(self._contains_secret_ref(item) for item in value)
        return False

    def _redacted_secret_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Build redacted payload for secret references."""
        redacted = {}
        secret_ref = payload.get("secret_ref")
        if secret_ref:
            redacted["secret_ref"] = secret_ref
        signing_policy_ref = payload.get("signing_policy_ref")
        if signing_policy_ref:
            redacted["signing_policy_ref"] = signing_policy_ref
        return redacted

    async def _resolve_secrets(self, value: Any) -> tuple[Any, Any]:
        if isinstance(value, dict):
            if "secret_ref" in value:
                secret_ref = value.get("secret_ref")
                if not secret_ref:
                    raise ValidationError("secret_ref is required for secret injection")
                if not self.secrets_port:
                    raise ValidationError("Secrets port not configured for secret injection")
                secret_value = await self.secrets_port.get_secret(secret_ref=secret_ref)
                return secret_value, self._redacted_secret_payload(value)
            resolved: dict[str, Any] = {}
            redacted: dict[str, Any] = {}
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

    def _first_url(self, value: Any) -> str | None:
        if isinstance(value, dict):
            for item in value.values():
                url = self._first_url(item)
                if url:
                    return url
        if isinstance(value, list):
            for item in value:
                url = self._first_url(item)
                if url:
                    return url
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            return value
        return None

    def _egress_decision(self, tool_ref: str, parameters: dict[str, Any], *, success: bool) -> dict[str, Any] | None:
        url = self._first_url(parameters)
        if not url:
            return None
        return {
            "decision": "allow" if success else "deny",
            "url": url,
            "tool_ref": tool_ref,
        }

    def _tool_call_metrics(
        self,
        *,
        tool_ref: str,
        parameters: dict[str, Any],
        status: str,
        result: Any | None = None,
        metadata: dict[str, Any] | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        request = ToolCallRequest(
            id=metadata.get("id") if metadata else "",
            tool_ref=tool_ref,
            arguments=parameters or {},
            metadata=metadata or {},
        )
        call_result = ToolCallResult(
            id=request.id,
            tool_ref=tool_ref,
            success=status == "completed",
            result={"result": result} if result is not None else {},
            error=(
                ToolCallError(code=error_code or "TOOL_ERROR", message=error_message or "")
                if error_code or error_message
                else None
            ),
            metadata=metadata or {},
        )
        result_payload = call_result.result if isinstance(call_result.result, dict) else {}
        error = call_result.error
        return {
            "tool_call": {
                "tool_name": tool_ref,
                "tool_ref": tool_ref,
                "tool_type": _provider_from_tool_ref(tool_ref) or "tool",
                "status": status,
                "arguments": summarize_parameters(request.arguments),
                "result": summarize_tool_payload(result_payload),
                "metadata": summarize_tool_payload(call_result.metadata),
                "error_code": error.code if error else None,
                "error_message": error.message if error else None,
            }
        }

    async def invoke(
        self,
        tool_ref: str,
        parameters: dict[str, Any],
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
        tool_execution_service = None
        tool_execution_claim = None
        timeout_seconds = float(kwargs.get("timeout_s") or self.timeout_seconds)
        redacted_parameters = parameters
        resolved_parameters = parameters
        if self._contains_secret_ref(parameters):
            if not self.secrets_port:
                raise ValidationError("Secrets port not configured for secret injection")
            resolved_parameters, redacted_parameters = await self._resolve_secrets(parameters)
        if self.trace_writer:
            run_id = resolve_run_id(kwargs, self.ctx)
            if not run_id:
                raise ValueError("run_id is required when trace_writer is enabled")
            tool_call_id = str(kwargs.get("tool_call_id") or f"call_{generate_ulid()}")
            idempotency_key = str(
                kwargs.get("idempotency_key") or f"tool:{run_id}:{tool_call_id}"
            )
            tool_execution_service = RuntimeToolExecutionService(
                db=self.trace_writer.db,
                ctx=self.ctx,
                trace_writer=self.trace_writer,
                lease_owner=str(
                    kwargs.get("lease_owner")
                    or self.ctx.request_id
                    or f"tool:{run_id}"
                ),
                lease_seconds=max(60, math.ceil(timeout_seconds) + 10),
                storage_port=self.storage_port,
            )
            tool_execution_claim = tool_execution_service.claim(
                ToolExecutionCommand(
                    run_id=run_id,
                    run_step_id=(str(kwargs["run_step_id"]) if kwargs.get("run_step_id") else None),
                    tool_call_id=tool_call_id,
                    tool_ref=tool_ref,
                    arguments=redacted_parameters,
                    idempotency_key=idempotency_key,
                    created_by=self.ctx.user_id,
                    resume_approval=bool(kwargs.get("resume_approval", False)),
                    retry_failed=bool(kwargs.get("retry_failed", False)),
                )
            )
            step = tool_execution_claim.run_step
            if tool_execution_claim.replayed:
                cached_response = await tool_execution_service.load_cached_response(
                    tool_execution_claim
                )
                if cached_response is not None:
                    return cached_response
            tool_execution_service.mark_running(tool_execution_claim.record.id)
            kwargs = {
                **kwargs,
                "tool_call_id": tool_call_id,
                "idempotency_key": idempotency_key,
                "run_step_id": step.id,
            }

        start_time = utc_now()
        try:
            # Generic URL egress checks apply to HTTP tools. Registry-backed
            # non-HTTP tools may accept URL-shaped business inputs without
            # performing network egress; adapter-level checks still run later.
            if self.enable_egress_check and tool_ref.startswith("tool:http:"):
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

            async def _invoke():
                if tool_execution_service and tool_execution_claim:
                    tool_execution_service.renew_lease(tool_execution_claim.record.id)
                return await self.gateway.invoke(
                    tool_ref=tool_ref,
                    parameters=resolved_parameters,
                    **kwargs,
                )

            with self.otel_tracer.start_as_current_span(
                "soit.tool.invoke",
                attributes={
                    "soit.tool.ref": tool_ref,
                    "soit.tool.provider": _provider_from_tool_ref(tool_ref) or "unknown",
                    "soit.tenant.id": self.ctx.tenant_id,
                    "soit.workspace.id": self.ctx.workspace_id,
                    "soit.run.id": resolve_run_id(kwargs, self.ctx) or "",
                    "soit.step.id": step.id if step else "",
                },
            ) as span:
                response = await run_with_timeout_retry(
                    _invoke,
                    timeout_seconds=timeout_seconds,
                    # Durable Agent calls are at-most-once at this boundary.
                    # Not every downstream adapter can honor an idempotency key.
                    max_retries=1 if kwargs.get("idempotency_key") else self.max_retries,
                    timeout_factory=lambda: TimeoutError(
                        f"Tool invocation timed out after {timeout_seconds} seconds",
                        {"timeout_seconds": timeout_seconds, "tool_ref": tool_ref},
                    ),
                    wait_min=1,
                    wait_max=5,
                )
                span.set_attribute("soit.tool.success", response.success)
            egress_decision = self._egress_decision(tool_ref, redacted_parameters, success=response.success)

            # Audit log
            if step and self.trace_writer:
                await log_gateway_request(
                    trace_writer=self.trace_writer,
                    run_id=resolve_run_id(kwargs, self.ctx),
                    step_id=step.id,
                    gateway_type="tool",
                    request_data={
                        "tool_ref": tool_ref,
                        "parameters": redacted_parameters,
                        "egress": egress_decision,
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
                    "egress": egress_decision,
                    **self._tool_call_metrics(
                        tool_ref=tool_ref,
                        parameters=redacted_parameters,
                        status="completed" if response.success else "failed",
                        result=response.result if response.success else None,
                        metadata=response.metadata,
                        error_code=None if response.success else "TOOL_ERROR",
                        error_message=response.error,
                    ),
                    **response.metadata,
                }
                tool_error_details = None
                if not response.success:
                    tool_error_details = {
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
                    error_details=tool_error_details,
                )
                self.trace_writer.record_cost(
                    run_id=resolve_run_id(kwargs, self.ctx),
                    step_id=step.id,
                    unit="requests",
                    quantity=1,
                    provider=_provider_from_tool_ref(tool_ref),
                    tool_ref=tool_ref,
                )

            if tool_execution_service and tool_execution_claim:
                await tool_execution_service.complete(tool_execution_claim.record.id, response)

            return response
        except Exception as e:
            if step and self.trace_writer:
                try:
                    await log_gateway_request(
                        trace_writer=self.trace_writer,
                        run_id=resolve_run_id(kwargs, self.ctx),
                        step_id=step.id,
                        gateway_type="tool",
                        request_data={
                            "tool_ref": tool_ref,
                            "parameters": redacted_parameters,
                            "egress": self._egress_decision(tool_ref, redacted_parameters, success=False),
                        },
                        response_data={
                            "success": False,
                            "error": str(e),
                            "error_type": type(e).__name__,
                            "details": error_details(e),
                        },
                        storage_port=self.storage_port,
                    )
                except Exception:
                    pass
                self.trace_writer.update_step_status(
                    step.id,
                    "failed",
                    metrics=self._tool_call_metrics(
                        tool_ref=tool_ref,
                        parameters=redacted_parameters,
                        status="failed",
                        error_code="TOOL_ERROR",
                        error_message=str(e),
                    ),
                    error_code="TOOL_ERROR",
                    error_message=str(e),
                    error_details=error_details(e),
                )
            if tool_execution_service and tool_execution_claim:
                tool_execution_service.fail(tool_execution_claim.record.id, e)
            raise
