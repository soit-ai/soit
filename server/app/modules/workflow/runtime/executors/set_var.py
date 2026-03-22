""" set_var

SetVar node executor.
"""

from typing import Dict, Any
from app.modules.workflow.runtime.executors.base import NodeExecutor, ExecutionContext
from app.kernel.commons.errors import ValidationError


class SetVarNodeExecutor(NodeExecutor):
    """Executor for set_var nodes."""

    async def execute(
        self,
        node: Dict[str, Any],
        context: ExecutionContext,
        inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
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
