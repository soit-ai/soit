""" output

Output node executor.
"""

from typing import Dict, Any
from app.modules.workflow.runtime.executors.base import NodeExecutor, ExecutionContext


class OutputNodeExecutor(NodeExecutor):
    """Executor for output nodes."""
    
    async def execute(
        self,
        node: Dict[str, Any],
        context: ExecutionContext,
        inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
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

