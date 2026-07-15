""" output

Output node executor.
"""

from typing import Any

from app.modules.workflow.runtime.executors.base import ExecutionContext, NodeExecutor


class OutputNodeExecutor(NodeExecutor):
    """Executor for output nodes."""

    async def execute(
        self,
        node: dict[str, Any],
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute output node.

        Args:
            node: Node definition.
            context: Execution context.
            inputs: Resolved inputs.

        Returns:
            Final output dictionary.
        """
        # Output node simply returns the inputs as final output
        # In production, could apply output schema validation here
        return inputs

