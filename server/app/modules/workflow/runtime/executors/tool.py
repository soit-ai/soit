""" tool

Tool node executor.
"""

from typing import Any

from app.kernel.commons.errors import ValidationError
from app.modules.workflow.runtime.executors.base import ExecutionContext, NodeExecutor


class ToolNodeExecutor(NodeExecutor):
    """Executor for tool nodes."""

    async def execute(
        self,
        node: dict[str, Any],
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute tool node.

        Args:
            node: Node definition.
            context: Execution context.
            inputs: Resolved inputs.

        Returns:
            Output dictionary with tool result.
        """
        if not context.tool_port:
            raise ValidationError("Tool port not available")

        # Extract tool reference
        registry_only = bool(context.workflow_policy.get("registry_only_tools"))
        tool_ref = inputs.get("tool_ref") or inputs.get("tool")
        if not tool_ref:
            raise ValidationError("Tool node requires 'tool_ref' or 'tool' input")
        if registry_only and not inputs.get("tool_ref"):
            raise ValidationError("Tool node requires 'tool_ref' when registry_only_tools is enabled")

        # Extract parameters (everything except tool_ref)
        parameters = {k: v for k, v in inputs.items() if k not in ("tool_ref", "tool")}
        linked_response = None

        def build_tool_metrics(
            *,
            status: str,
            result: dict[str, Any] | None = None,
            metadata: dict[str, Any] | None = None,
            tool_type: str = "builtin",
            error_code: str | None = None,
            error_message: str | None = None,
        ) -> dict[str, Any]:
            return {
                "tool_call": {
                    "tool_name": tool_ref,
                    "tool_ref": tool_ref,
                    "tool_type": tool_type,
                    "status": status,
                    "arguments": parameters,
                    "result": result or {},
                    "metadata": metadata or {},
                    "error_code": error_code,
                    "error_message": error_message,
                }
            }

        if context.response_service:
            linked_response = context.response_service.create_linked_response(
                run_id=context.run_id,
                input_json={
                    "tool_ref": tool_ref,
                    "parameters": parameters,
                    "node_id": node.get("id"),
                    "node_type": node.get("type"),
                    "source": "workflow.tool_node",
                },
                metadata_json={
                    "source": "workflow.tool_node",
                    "step_id": context.step_id,
                    "node_id": node.get("id"),
                    "node_type": node.get("type"),
                },
            )
            linked_response = context.response_service.mark_running(linked_response)
            context.response_service.append_event(
                response=linked_response,
                event_type="tool.call.requested",
                payload={
                    "response_id": linked_response.id,
                    "run_id": linked_response.run_id,
                    "tool_call_id": context.step_id,
                    "tool_name": tool_ref,
                    "tool_type": "builtin",
                    "step_id": context.step_id,
                    "status": "requested",
                    "arguments": parameters,
                },
                source="workflow",
            )

        approval_gateway = context.approval_checkpoint_gateway
        if approval_gateway is not None:
            approval_request = {
                "action": "invoke",
                "resource_type": "tool",
                "resource_ref": tool_ref,
                "risk_level": str(inputs.get("risk_level") or node.get("risk_level") or "normal"),
                "run_id": context.run_id,
                "task_id": context.task_id,
                "thread_id": context.thread_id,
                "agent_id": context.agent_id,
                "title": f"Approve tool call: {tool_ref}",
                "details": {
                    "node_id": node.get("id"),
                    "tool_ref": tool_ref,
                    "parameters": parameters,
                },
            }
            decision = approval_gateway.evaluate(context.ctx, approval_request)
            if bool(getattr(decision, "requires_approval", False)):
                approval_status = str(getattr(decision, "task_status", None) or "waiting_approval")
                policy_ref = getattr(decision, "policy_ref", None)
                reason = str(getattr(decision, "reason", "approval_required"))
                approval_payload = dict(getattr(decision, "approval_payload", None) or {})
                metadata = {
                    "source": "workflow.tool_node",
                    "node_id": node.get("id"),
                    "reason": reason,
                    "policy_ref": policy_ref,
                }
                if context.trace_writer and context.step_id:
                    context.trace_writer.update_step_metrics(
                        context.step_id,
                        build_tool_metrics(
                            status=approval_status,
                            metadata=metadata,
                        ),
                    )
                if linked_response:
                    context.response_service.append_event(
                        response=linked_response,
                        event_type="tool.call.approval_required",
                        payload={
                            "response_id": linked_response.id,
                            "run_id": linked_response.run_id,
                            "tool_call_id": context.step_id,
                            "tool_name": tool_ref,
                            "tool_type": "builtin",
                            "step_id": context.step_id,
                            "status": approval_status,
                            "policy_ref": policy_ref,
                            "reason": reason,
                            "approval": approval_payload,
                        },
                        source="workflow",
                    )
                output = {
                    "status": approval_status,
                    "approval": approval_payload,
                    "metadata": metadata,
                }
                if linked_response:
                    output["response_id"] = linked_response.id
                return output

        if linked_response:
            context.response_service.append_event(
                response=linked_response,
                event_type="tool.call.started",
                payload={
                    "response_id": linked_response.id,
                    "run_id": linked_response.run_id,
                    "tool_call_id": context.step_id,
                    "tool_name": tool_ref,
                    "tool_type": "builtin",
                    "step_id": context.step_id,
                    "status": "started",
                },
                source="workflow",
            )
        if context.trace_writer and context.step_id:
            context.trace_writer.update_step_metrics(
                context.step_id,
                build_tool_metrics(
                    status="started",
                    metadata={"source": "workflow.tool_node", "node_id": node.get("id")},
                ),
            )

        try:
            response = await context.tool_port.invoke(
                tool_ref=tool_ref,
                parameters=parameters,
                run_id=context.run_id,
                ctx=context.ctx,
                strict_registry=registry_only,
            )
        except Exception as exc:
            if context.trace_writer and context.step_id:
                context.trace_writer.update_step_metrics(
                    context.step_id,
                    build_tool_metrics(
                        status="failed",
                        metadata={"source": "workflow.tool_node", "node_id": node.get("id")},
                        error_code="tool_execution_failed",
                        error_message=str(exc),
                    ),
                )
            if linked_response:
                linked_response = context.response_service.fail_response(
                    response=linked_response,
                    error_code="workflow_tool_failed",
                    error_message=str(exc),
                    source="workflow",
                    failed_event_payload={
                        "response_id": linked_response.id,
                        "run_id": linked_response.run_id,
                        "step_id": context.step_id,
                        "node_id": node.get("id"),
                        "status": "failed",
                        "error": {"code": "workflow_tool_failed", "message": str(exc)},
                    },
                )
                context.response_service.append_event(
                    response=linked_response,
                    event_type="tool.call.failed",
                    payload={
                        "response_id": linked_response.id,
                        "run_id": linked_response.run_id,
                        "tool_call_id": context.step_id,
                        "tool_name": tool_ref,
                        "tool_type": "builtin",
                        "step_id": context.step_id,
                        "status": "failed",
                        "error": {"code": "tool_execution_failed", "message": str(exc)},
                    },
                    source="workflow",
                )
            raise

        if not response.success:
            response_metadata = response.metadata or {}
            effective_tool_type = str(response_metadata.get("source_kind") or "builtin")
            if context.trace_writer and context.step_id:
                context.trace_writer.update_step_metrics(
                    context.step_id,
                    build_tool_metrics(
                        status="failed",
                        metadata={"source": "workflow.tool_node", "node_id": node.get("id"), **response_metadata},
                        tool_type=effective_tool_type,
                        error_code="tool_execution_failed",
                        error_message=response.error or "Tool execution failed",
                    ),
                )
            if linked_response:
                linked_response = context.response_service.fail_response(
                    response=linked_response,
                    error_code="workflow_tool_failed",
                    error_message=response.error or "Tool execution failed",
                    source="workflow",
                    failed_event_payload={
                        "response_id": linked_response.id,
                        "run_id": linked_response.run_id,
                        "step_id": context.step_id,
                        "node_id": node.get("id"),
                        "status": "failed",
                        "error": {"code": "workflow_tool_failed", "message": response.error or "Tool execution failed"},
                    },
                )
                context.response_service.append_event(
                    response=linked_response,
                    event_type="tool.call.failed",
                    payload={
                        "response_id": linked_response.id,
                        "run_id": linked_response.run_id,
                        "tool_call_id": context.step_id,
                        "tool_name": tool_ref,
                        "tool_type": effective_tool_type,
                        "step_id": context.step_id,
                        "status": "failed",
                        "error": {"code": "tool_execution_failed", "message": response.error or "Tool execution failed"},
                    },
                    source="workflow",
                )
            raise ValidationError(f"Tool execution failed: {response.error}")

        response_metadata = response.metadata or {}
        effective_tool_type = str(response_metadata.get("source_kind") or "builtin")
        result_payload = response.result if isinstance(response.result, dict) else {"value": response.result}
        result_payload = {**result_payload, "tool_ref": result_payload.get("tool_ref") or tool_ref}
        if context.trace_writer and context.step_id:
            context.trace_writer.update_step_metrics(
                context.step_id,
                build_tool_metrics(
                    status="completed",
                    result={"result": result_payload},
                    metadata={"source": "workflow.tool_node", "node_id": node.get("id"), **response_metadata},
                    tool_type=effective_tool_type,
                ),
            )
        if linked_response:
            output_payload = {
                "result": result_payload,
                "metadata": response_metadata,
                "tool_ref": tool_ref,
            }
            linked_response = context.response_service.complete_response(
                response=linked_response,
                output_json=output_payload,
                usage_json={},
                source="workflow",
                output_event_type=None,
                completed_event_type=None,
                completed_event_payload={
                    "response_id": linked_response.id,
                    "run_id": linked_response.run_id,
                    "step_id": context.step_id,
                    "node_id": node.get("id"),
                    "status": "succeeded",
                    "output": output_payload,
                },
            )
            context.response_service.append_event(
                response=linked_response,
                event_type="tool.call.completed",
                payload={
                    "response_id": linked_response.id,
                    "run_id": linked_response.run_id,
                    "tool_call_id": context.step_id,
                    "tool_name": tool_ref,
                    "tool_type": effective_tool_type,
                    "step_id": context.step_id,
                    "status": "succeeded",
                    "result": {"result": result_payload},
                    "metadata": response_metadata,
                },
                source="workflow",
            )
            context.response_service.append_event(
                response=linked_response,
                event_type="response.succeeded",
                payload={
                    "response_id": linked_response.id,
                    "run_id": linked_response.run_id,
                    "step_id": context.step_id,
                    "node_id": node.get("id"),
                    "status": "succeeded",
                    "output": output_payload,
                },
                source="workflow",
            )

        output = {
            "result": result_payload,
            "metadata": response_metadata,
        }
        if linked_response:
            output["response_id"] = linked_response.id
        return output
