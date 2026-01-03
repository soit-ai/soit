""" transform

Transform node executor.
"""

from typing import Dict, Any, List
from app.modules.workflow.runtime.executors.base import NodeExecutor, ExecutionContext


class TransformNodeExecutor(NodeExecutor):
    """Executor for transform nodes."""
    
    async def execute(
        self,
        node: Dict[str, Any],
        context: ExecutionContext,
        inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute transform node.
        
        Args:
            node: Node definition.
            context: Execution context.
            inputs: Resolved inputs.
            
        Returns:
            Transformed output dictionary.
        """
        # Extract transformation rules
        mapping = inputs.get("mapping") or inputs.get("transform")
        
        if mapping:
            # Apply mapping transformation
            output = {}
            for key, value in mapping.items():
                if isinstance(value, str) and value.startswith("{{") and value.endswith("}}"):
                    # Variable reference
                    var_path = value[2:-2].strip()
                    output[key] = self._get_nested_value(inputs, var_path)
                else:
                    output[key] = value
            return output
        
        # Default: pass through inputs
        return inputs
    
    def _get_nested_value(self, obj: Dict[str, Any], path: str) -> Any:
        """Get nested value using dot notation.
        
        Args:
            obj: Object to get value from.
            path: Dot-separated path.
            
        Returns:
            Value at path.
        """
        parts = path.split(".")
        current = obj
        
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list) and part.isdigit():
                current = current[int(part)]
            else:
                return None
            
            if current is None:
                return None
        
        return current

