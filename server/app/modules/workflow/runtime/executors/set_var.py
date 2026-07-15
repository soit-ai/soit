""" set_var

SetVar node executor.
"""

from typing import Any

from app.kernel.commons.errors import ValidationError
from app.modules.workflow.runtime.executors.base import ExecutionContext, NodeExecutor


class SetVarNodeExecutor(NodeExecutor):
    """Executor for set_var nodes."""

    async def execute(
        self,
        node: dict[str, Any],
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute set_var node."""
        if "set" in inputs and isinstance(inputs["set"], dict):
            return inputs["set"]

        key = inputs.get("key")
        if not key:
            raise ValidationError("SetVar node requires 'key' or 'set' input")

        return {
            "key": key,
            "value": inputs.get("value"),
        }
