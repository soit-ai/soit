""" policy

Default policies for plugin runtime invocation.
"""

from __future__ import annotations

from typing import Any

from app.kernel.commons.errors import TimeoutError
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.common.audit import log_gateway_request
from app.kernel.ports.common.policy import (
    error_details,
    resolve_run_id,
    run_with_timeout_retry,
)
from app.kernel.ports.plugins.interface import PluginRuntimePort
from app.kernel.ports.storage.interface import StoragePort
from app.kernel.runtime.runs.writer import TraceWriter

DEFAULT_PLUGIN_TIMEOUT_S: float = 30.0


def _resolve_run_id(kwargs: dict[str, Any], ctx: RequestContext) -> str:
    return resolve_run_id(kwargs, ctx)


def _error_details(exc: Exception) -> dict[str, Any]:
    return error_details(exc)


def _plugin_tool_ref(plugin_name: str, tool_name: str) -> str:
    return f"{plugin_name}:{tool_name}"


class PluginRuntimePolicyGateway(PluginRuntimePort):
    """Plugin runtime port with trace/audit enforcement."""

    def __init__(
        self,
        gateway: PluginRuntimePort,
        ctx: RequestContext,
        trace_writer: TraceWriter | None = None,
        storage_port: StoragePort | None = None,
        timeout_seconds: int = DEFAULT_PLUGIN_TIMEOUT_S,
    ) -> None:
        self.gateway = gateway
        self.ctx = ctx
        self.trace_writer = trace_writer
        self.storage_port = storage_port
        self.timeout_seconds = timeout_seconds

    def list_tools(
        self,
        *,
        plugin_name: str,
        version: str,
        ctx: RequestContext,
    ) -> list[dict[str, Any]]:
        return self.gateway.list_tools(plugin_name=plugin_name, version=version, ctx=ctx)

    def resolve_skill_context(
        self,
        *,
        skill_refs: list[str],
        ctx: RequestContext,
    ) -> str | None:
        return self.gateway.resolve_skill_context(skill_refs=skill_refs, ctx=ctx)

    async def invoke(
        self,
        *,
        plugin_name: str,
        version: str,
        tool_name: str,
        input_json: dict[str, Any],
        ctx: RequestContext,
        timeout_s: float | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        step = None
        if self.trace_writer:
            run_id = _resolve_run_id(kwargs, self.ctx)
            if not run_id:
                raise ValueError("run_id is required when trace_writer is enabled")
            step = self.trace_writer.create_step(
                run_id=run_id,
                step_type="tool",
                input_summary=f"plugin={plugin_name}:{tool_name}",
            )
            self.trace_writer.update_step_status(step.id, "running")

        start_time = utc_now()
        try:
            effective_timeout = timeout_s or self.timeout_seconds

            async def _invoke():
                return await self.gateway.invoke(
                        plugin_name=plugin_name,
                        version=version,
                        tool_name=tool_name,
                        input_json=input_json,
                        ctx=ctx,
                        timeout_s=timeout_s,
                )

            response = await run_with_timeout_retry(
                _invoke,
                timeout_seconds=effective_timeout,
                max_retries=1,
                timeout_factory=lambda: TimeoutError(
                    f"Plugin invocation timed out after {effective_timeout} seconds",
                    {"plugin": plugin_name, "tool": tool_name},
                ),
            )

            if step and self.trace_writer:
                await log_gateway_request(
                    trace_writer=self.trace_writer,
                    run_id=_resolve_run_id(kwargs, self.ctx),
                    step_id=step.id,
                    gateway_type="plugin",
                    request_data={
                        "plugin_name": plugin_name,
                        "version": version,
                        "tool_name": tool_name,
                        "input": input_json,
                    },
                    response_data={
                        "result": response,
                    },
                    storage_port=self.storage_port,
                )

                elapsed_ms = int((utc_now() - start_time).total_seconds() * 1000)
                self.trace_writer.update_step_status(
                    step.id,
                    "succeeded",
                    output_summary=str(response)[:100] if response else None,
                    metrics={
                        "latency_ms": elapsed_ms,
                        "plugin": plugin_name,
                        "tool": tool_name,
                    },
                )
                self.trace_writer.record_cost(
                    run_id=_resolve_run_id(kwargs, self.ctx),
                    step_id=step.id,
                    unit="requests",
                    quantity=1,
                    provider="plugin",
                    tool_ref=_plugin_tool_ref(plugin_name, tool_name),
                    source_port="plugins",
                    operation="invoke",
                    latency_ms=elapsed_ms,
                    request_count=1,
                )

            return response
        except Exception as exc:
            if step and self.trace_writer:
                self.trace_writer.update_step_status(
                    step.id,
                    "failed",
                    error_code="PLUGIN_ERROR",
                    error_message=str(exc),
                    error_details=_error_details(exc),
                )
            raise
