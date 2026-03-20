""" tool

Tool node executor.
"""

from typing import Dict, Any
from app.kernel.commons.time import utc_now
from app.modules.workflow.runtime.executors.base import NodeExecutor, ExecutionContext
from app.kernel.commons.errors import ValidationError


class ToolNodeExecutor(NodeExecutor):
    """Executor for tool nodes."""
    
    async def execute(
        self,
        node: Dict[str, Any],
        context: ExecutionContext,
        inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
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
            result: Dict[str, Any] | None = None,
            metadata: Dict[str, Any] | None = None,
            error_code: str | None = None,
            error_message: str | None = None,
        ) -> Dict[str, Any]:
            return {
                "tool_call": {
                    "tool_name": tool_ref,
                    "tool_ref": tool_ref,
                    "tool_type": "builtin",
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
            linked_response.status = "in_progress"
            linked_response = context.response_service.save_response(linked_response)
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
                linked_response.status = "failed"
                linked_response.error_code = "workflow_tool_failed"
                linked_response.error_message = str(exc)
                linked_response = context.response_service.save_response(linked_response)
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
                context.response_service.append_event(
                    response=linked_response,
                    event_type="response.failed",
                    payload={
                        "response_id": linked_response.id,
                        "run_id": linked_response.run_id,
                        "step_id": context.step_id,
                        "node_id": node.get("id"),
                        "status": linked_response.status,
                        "error": {"code": linked_response.error_code, "message": linked_response.error_message},
                    },
                    source="workflow",
                )
            raise

        if not response.success:
            if context.trace_writer and context.step_id:
                context.trace_writer.update_step_metrics(
                    context.step_id,
                    build_tool_metrics(
                        status="failed",
                        metadata={"source": "workflow.tool_node", "node_id": node.get("id"), **(response.metadata or {})},
                        error_code="tool_execution_failed",
                        error_message=response.error or "Tool execution failed",
                    ),
                )
            if linked_response:
                linked_response.status = "failed"
                linked_response.error_code = "workflow_tool_failed"
                linked_response.error_message = response.error or "Tool execution failed"
                linked_response = context.response_service.save_response(linked_response)
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
                        "error": {"code": "tool_execution_failed", "message": response.error or "Tool execution failed"},
                    },
                    source="workflow",
                )
                context.response_service.append_event(
                    response=linked_response,
                    event_type="response.failed",
                    payload={
                        "response_id": linked_response.id,
                        "run_id": linked_response.run_id,
                        "step_id": context.step_id,
                        "node_id": node.get("id"),
                        "status": linked_response.status,
                        "error": {"code": linked_response.error_code, "message": linked_response.error_message},
                    },
                    source="workflow",
                )
            raise ValidationError(f"Tool execution failed: {response.error}")

        if context.trace_writer and context.step_id:
            context.trace_writer.update_step_metrics(
                context.step_id,
                build_tool_metrics(
                    status="completed",
                    result={"result": response.result},
                    metadata={"source": "workflow.tool_node", "node_id": node.get("id"), **(response.metadata or {})},
                ),
            )
        if linked_response:
            linked_response.output_json = {
                "result": response.result,
                "metadata": response.metadata,
                "tool_ref": tool_ref,
            }
            linked_response.usage_json = {}
            linked_response.status = "completed"
            linked_response.completed_at = utc_now()
            linked_response.error_code = None
            linked_response.error_message = None
            linked_response = context.response_service.save_response(linked_response)
            context.response_service.append_event(
                response=linked_response,
                event_type="tool.call.completed",
                payload={
                    "response_id": linked_response.id,
                    "run_id": linked_response.run_id,
                    "tool_call_id": context.step_id,
                    "tool_name": tool_ref,
                    "tool_type": "builtin",
                    "step_id": context.step_id,
                    "status": "completed",
                    "result": {"result": response.result},
                    "metadata": response.metadata or {},
                },
                source="workflow",
            )
            context.response_service.append_event(
                response=linked_response,
                event_type="response.completed",
                payload={
                    "response_id": linked_response.id,
                    "run_id": linked_response.run_id,
                    "step_id": context.step_id,
                    "node_id": node.get("id"),
                    "status": linked_response.status,
                    "output": linked_response.output_json,
                },
                source="workflow",
            )
        
        output = {
            "result": response.result,
            "metadata": response.metadata,
        }
        if linked_response:
            output["response_id"] = linked_response.id
        return output
