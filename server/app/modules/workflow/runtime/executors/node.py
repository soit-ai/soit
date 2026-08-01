""" node

Registry-backed workflow node executor.
"""

from typing import Any

from app.kernel.commons.errors import ValidationError
from app.kernel.registry.deps import get_registry
from app.kernel.specs.validator import validate_spec
from app.modules.workflow.runtime.executors.base import ExecutionContext, NodeExecutor


class RegistryNodeExecutor(NodeExecutor):
    """Executor for registry-backed workflow nodes."""

    async def execute(
        self,
        node: dict[str, Any],
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute registry-backed node."""
        if not context.tool_port:
            raise ValidationError("Tool port not available")
        if not context.ctx:
            raise ValidationError("Request context not available")

        node_ref = inputs.get("node_ref") or inputs.get("node")
        if not node_ref:
            raise ValidationError("Node requires 'node_ref' input")

        parameters = inputs.get("parameters")
        if parameters is None:
            parameters = {
                k: v
                for k, v in inputs.items()
                if k not in ("node_ref", "node", "parameters")
            }
        if not isinstance(parameters, dict):
            raise ValidationError("Node parameters must be an object")

        reg = get_registry()
        found = reg.get_latest(
            kind="workflow_node",
            tenant_id=context.ctx.tenant_id,
            workspace_id=context.ctx.workspace_id,
            name=node_ref,
        )
        if not found:
            raise ValidationError(f"Workflow node not registered: {node_ref}")
        _, payload = found
        node_spec = payload.get("node_spec") or {}

        input_schema = node_spec.get("input_schema")
        if input_schema is None:
            raise ValidationError(f"Workflow node '{node_ref}' missing input_schema")
        validate_spec(parameters, input_schema)

        adapter = node_spec.get("adapter")
        if adapter == "builtin":
            node_type = node_spec.get("node_type")
            if not node_type or node_type == "node":
                raise ValidationError("Builtin workflow node requires a valid node_type")
            from app.modules.workflow.runtime.executors import get_executor

            executor_class = get_executor(node_type)
            executor = executor_class()
            output = await executor.execute(
                {"type": node_type, "input": parameters},
                context,
                parameters,
            )
            output_schema = node_spec.get("output_schema")
            if output_schema is not None:
                validate_spec(output, output_schema)
            return output

        if adapter != "tool":
            raise ValidationError(f"Unsupported workflow node adapter: {adapter}")

        tool_ref = node_spec.get("tool_ref")
        if not tool_ref:
            raise ValidationError(f"Workflow node '{node_ref}' missing tool_ref")

        # Attempt-stable identity: a retry or crash-resume must replay a
        # completed call from the ledger instead of reissuing it.
        tool_call_id = (
            f"workflow:{context.workflow_run_id or context.run_id}:"
            f"{node.get('id') or node_ref}:0"
        )
        response = await context.tool_port.invoke(
            tool_ref=tool_ref,
            parameters=parameters,
            run_id=context.run_id,
            ctx=context.ctx,
            strict_registry=True,
            tool_call_id=tool_call_id,
            idempotency_key=f"tool:{context.run_id}:{tool_call_id}",
            retry_failed=True,
        )
        if not response.success:
            raise ValidationError(f"Node execution failed: {response.error}")

        output = {"result": response.result, "metadata": response.metadata}
        output_schema = node_spec.get("output_schema")
        if output_schema is not None:
            validate_spec(output, output_schema)
        return output
