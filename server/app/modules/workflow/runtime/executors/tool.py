""" tool

Tool node executor.
"""

from typing import Any

from app.kernel.commons.errors import ValidationError
from app.kernel.runtime.db.models.runs import RunStep
from app.kernel.runtime.runs.tool_calls import (
    RuntimeToolExecutionService,
    ToolExecutionCommand,
    summarize_parameters,
    summarize_tool_payload,
)
from app.kernel.runtime.tools.approval import (
    resolve_tool_policy,
    tool_approval_rule,
)
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
        node_id = str(node.get("id") or "tool")
        resuming_approval = context.resume_approval_node_id == node_id
        node_attempt_step_id = str(context.step_id or "untraced")
        tool_call_id = str(
            context.resume_tool_call_id
            if resuming_approval and context.resume_tool_call_id
            else (
                f"workflow:{context.workflow_run_id or context.run_id}:"
                f"{node_id}:{node_attempt_step_id}"
            )
        )
        tool_run_step_id = None
        if (
            resuming_approval
            and context.trace_writer
            and context.resume_tool_run_step_id
        ):
            tool_step = context.trace_writer.db.get(
                RunStep,
                context.resume_tool_run_step_id,
            )
            if (
                tool_step is None
                or tool_step.run_id != context.run_id
                or tool_step.step_type != "tool"
                or tool_step.status != "waiting_approval"
            ):
                raise ValidationError("Workflow approval tool step is not resumable")
            tool_run_step_id = tool_step.id
        elif context.trace_writer:
            tool_step = context.trace_writer.create_step(
                run_id=context.run_id,
                step_type="tool",
                step_id=f"tool:{node_id}:{node_attempt_step_id}",
                input_summary=f"tool_ref={tool_ref}",
            )
            tool_run_step_id = tool_step.id
        linked_response = None
        tool_lease_owner = str(
            context.ctx.request_id or f"workflow:{context.run_id}"
        )
        tool_execution_service = (
            RuntimeToolExecutionService(
                db=context.trace_writer.db,
                ctx=context.ctx,
                trace_writer=context.trace_writer,
                lease_owner=tool_lease_owner,
            )
            if context.trace_writer
            else None
        )
        tool_execution_claim = None

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
                    "tool_call_id": tool_call_id,
                    "tool_name": tool_ref,
                    "tool_ref": tool_ref,
                    "tool_type": tool_type,
                    "status": status,
                    "arguments": summarize_parameters(parameters),
                    "result": summarize_tool_payload(result or {}),
                    "metadata": summarize_tool_payload(metadata or {}),
                    "error_code": error_code,
                    "error_message": error_message,
                }
            }

        if (
            resuming_approval
            and context.response_service
            and context.resume_response_id
        ):
            linked_response = context.response_service.get_response(
                context.resume_response_id
            )
        elif context.response_service:
            linked_response = context.response_service.create_linked_response(
                run_id=context.run_id,
                input_json={
                    "tool_ref": tool_ref,
                    "parameters": summarize_parameters(parameters),
                    "node_id": node.get("id"),
                    "node_type": node.get("type"),
                    "source": "workflow.tool_node",
                },
                metadata_json={
                    "source": "workflow.tool_node",
                    "step_id": tool_run_step_id,
                    "node_id": node.get("id"),
                    "node_type": node.get("type"),
                },
            )
            linked_response = context.response_service.mark_running(linked_response)

        tool_policy = resolve_tool_policy(
            tool_ref=str(tool_ref),
            ctx=context.ctx,
            tool_port=context.tool_port,
        )
        approval_rule = tool_approval_rule(tool_policy)
        approval_gateway = context.approval_checkpoint_gateway
        if not resuming_approval and (
            approval_gateway is not None or approval_rule.required
        ):
            requested_risk_level = str(
                inputs.get("risk_level") or node.get("risk_level") or "normal"
            )
            risk_level = (
                approval_rule.risk_level
                if approval_rule.required
                else requested_risk_level
            )
            approval_request = {
                "action": "invoke",
                "resource_type": "tool",
                "resource_ref": tool_ref,
                "risk_level": risk_level,
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
            decision = (
                approval_gateway.evaluate(context.ctx, approval_request)
                if approval_gateway is not None
                else None
            )
            gateway_requires_approval = bool(
                getattr(decision, "requires_approval", False)
            )
            if approval_rule.required or gateway_requires_approval:
                approval_status = str(getattr(decision, "task_status", None) or "waiting_approval")
                policy_ref = (
                    getattr(decision, "policy_ref", None)
                    if gateway_requires_approval
                    else f"tool_spec:{tool_ref}"
                )
                reason = (
                    str(getattr(decision, "reason", "approval_required"))
                    if gateway_requires_approval
                    else "tool_spec_approval_required"
                )
                approval_payload = dict(
                    getattr(decision, "approval_payload", None)
                    or {
                        "title": f"Approve tool call: {tool_ref}",
                        "risk_level": risk_level,
                    }
                )
                metadata = {
                    "source": "workflow.tool_node",
                    "node_id": node.get("id"),
                    "reason": reason,
                    "policy_ref": policy_ref,
                    "risk_level": risk_level,
                }
                if tool_execution_service is not None and tool_run_step_id:
                    waiting_claim = tool_execution_service.prepare_waiting_approval(
                        ToolExecutionCommand(
                            run_id=context.run_id,
                            run_step_id=tool_run_step_id,
                            tool_call_id=tool_call_id,
                            tool_ref=tool_ref,
                            arguments=parameters,
                            idempotency_key=f"tool:{context.run_id}:{tool_call_id}",
                            created_by=context.ctx.user_id,
                        )
                    )
                    tool_run_step_id = waiting_claim.run_step.id
                    context.trace_writer.update_step_metrics(
                        tool_run_step_id,
                        build_tool_metrics(
                            status=approval_status,
                            metadata=metadata,
                        ),
                    )
                if linked_response:
                    context.response_service.append_event(
                        response=linked_response,
                        event_type="tool.call.requested",
                        payload={
                            "response_id": linked_response.id,
                            "run_id": linked_response.run_id,
                            "tool_call_id": tool_call_id,
                            "tool_name": tool_ref,
                            "tool_type": "builtin",
                            "step_id": tool_run_step_id,
                            "status": "requested",
                            "arguments": summarize_parameters(parameters),
                        },
                        source="workflow",
                    )
                    context.response_service.append_event(
                        response=linked_response,
                        event_type="tool.call.approval_required",
                        payload={
                            "response_id": linked_response.id,
                            "run_id": linked_response.run_id,
                            "tool_call_id": tool_call_id,
                            "tool_name": tool_ref,
                            "tool_type": "builtin",
                            "step_id": tool_run_step_id,
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
                    "tool_call_id": tool_call_id,
                    "tool_run_step_id": tool_run_step_id,
                }
                if linked_response:
                    output["response_id"] = linked_response.id
                return output

        if tool_execution_service is not None:
            tool_execution_claim = tool_execution_service.claim(
                ToolExecutionCommand(
                    run_id=context.run_id,
                    run_step_id=tool_run_step_id,
                    tool_call_id=tool_call_id,
                    tool_ref=tool_ref,
                    arguments=parameters,
                    idempotency_key=f"tool:{context.run_id}:{tool_call_id}",
                    created_by=context.ctx.user_id,
                    resume_approval=resuming_approval,
                )
            )
            tool_run_step_id = tool_execution_claim.run_step.id
        if linked_response:
            if not resuming_approval:
                context.response_service.append_event(
                    response=linked_response,
                    event_type="tool.call.requested",
                    payload={
                        "response_id": linked_response.id,
                        "run_id": linked_response.run_id,
                        "tool_call_id": tool_call_id,
                        "tool_name": tool_ref,
                        "tool_type": "builtin",
                        "step_id": tool_run_step_id,
                        "status": "requested",
                        "arguments": summarize_parameters(parameters),
                    },
                    source="workflow",
                )
            context.response_service.append_event(
                response=linked_response,
                event_type="tool.call.started",
                payload={
                    "response_id": linked_response.id,
                    "run_id": linked_response.run_id,
                    "tool_call_id": tool_call_id,
                    "tool_name": tool_ref,
                    "tool_type": "builtin",
                    "step_id": tool_run_step_id,
                    "status": "started",
                },
                source="workflow",
            )
        if context.trace_writer and tool_run_step_id:
            context.trace_writer.update_step_metrics(
                tool_run_step_id,
                build_tool_metrics(
                    status="started",
                    metadata={"source": "workflow.tool_node", "node_id": node.get("id")},
                ),
            )

        try:
            if tool_execution_claim is not None and tool_execution_claim.replayed:
                response = await tool_execution_service.load_cached_response(
                    tool_execution_claim
                )
                if response is None:
                    raise RuntimeError("Durable workflow tool replay is unavailable")
            else:
                if tool_execution_claim is not None:
                    tool_execution_service.mark_running(tool_execution_claim.record.id)
                response = await context.tool_port.invoke(
                    tool_ref=tool_ref,
                    parameters=parameters,
                    run_id=context.run_id,
                    ctx=context.ctx,
                    strict_registry=registry_only,
                    tool_call_id=tool_call_id,
                    idempotency_key=f"tool:{context.run_id}:{tool_call_id}",
                    run_step_id=tool_run_step_id,
                    resume_approval=resuming_approval,
                    lease_owner=tool_lease_owner,
                )
                if tool_execution_claim is not None:
                    await tool_execution_service.complete(
                        tool_execution_claim.record.id,
                        response,
                    )
        except Exception as exc:
            if tool_execution_claim is not None and not tool_execution_claim.replayed:
                tool_execution_service.fail(tool_execution_claim.record.id, exc)
            if context.trace_writer and tool_run_step_id:
                context.trace_writer.update_step_metrics(
                    tool_run_step_id,
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
                        "step_id": tool_run_step_id,
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
                        "tool_call_id": tool_call_id,
                        "tool_name": tool_ref,
                        "tool_type": "builtin",
                        "step_id": tool_run_step_id,
                        "status": "failed",
                        "error": {"code": "tool_execution_failed", "message": str(exc)},
                    },
                    source="workflow",
                )
            raise

        if not response.success:
            response_metadata = response.metadata or {}
            effective_tool_type = str(response_metadata.get("source_kind") or "builtin")
            if context.trace_writer and tool_run_step_id:
                context.trace_writer.update_step_metrics(
                    tool_run_step_id,
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
                        "step_id": tool_run_step_id,
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
                        "tool_call_id": tool_call_id,
                        "tool_name": tool_ref,
                        "tool_type": effective_tool_type,
                        "step_id": tool_run_step_id,
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
        persisted_result = summarize_tool_payload(result_payload)
        persisted_metadata = summarize_tool_payload(response_metadata)
        if context.trace_writer and tool_run_step_id:
            context.trace_writer.update_step_metrics(
                tool_run_step_id,
                build_tool_metrics(
                    status="completed",
                    result={"result": result_payload},
                    metadata={"source": "workflow.tool_node", "node_id": node.get("id"), **response_metadata},
                    tool_type=effective_tool_type,
                ),
            )
        if linked_response:
            output_payload = {
                "result": persisted_result,
                "metadata": persisted_metadata,
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
                    "step_id": tool_run_step_id,
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
                    "tool_call_id": tool_call_id,
                    "tool_name": tool_ref,
                    "tool_type": effective_tool_type,
                    "step_id": tool_run_step_id,
                    "status": "succeeded",
                    "result": summarize_tool_payload({"result": result_payload}),
                    "metadata": persisted_metadata,
                },
                source="workflow",
            )
            context.response_service.append_event(
                response=linked_response,
                event_type="response.succeeded",
                payload={
                    "response_id": linked_response.id,
                    "run_id": linked_response.run_id,
                    "step_id": tool_run_step_id,
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
