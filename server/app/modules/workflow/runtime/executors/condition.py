""" condition

Condition node executor.
"""

from typing import Any

from app.kernel.commons.errors import ValidationError
from app.modules.workflow.runtime.executors.base import ExecutionContext, NodeExecutor


class ConditionNodeExecutor(NodeExecutor):
    """Executor for condition nodes."""

    async def execute(
        self,
        node: dict[str, Any],
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute condition node.

        Args:
            node: Node definition.
            context: Execution context.
            inputs: Resolved inputs.

        Returns:
            Output dictionary with 'result' (boolean) and 'value'.
        """
        # Extract condition expression
        condition = inputs.get("condition")
        if condition is None:
            raise ValidationError("Condition node requires 'condition' input")

        # Evaluate condition
        # Support simple comparisons: "value > 0", "status == 'success'", etc.
        result = self._evaluate_condition(condition, inputs)

        return {
            "result": result,
            "value": result,
        }

    def _evaluate_condition(self, condition: Any, inputs: dict[str, Any]) -> bool:
        """Evaluate condition expression.

        Args:
            condition: Condition value or expression.
            inputs: Input values for evaluation.

        Returns:
            Boolean result.
        """
        # If condition is already a boolean, return it
        if isinstance(condition, bool):
            return condition

        # If condition is a string, try to evaluate as expression
        if isinstance(condition, str):
            normalized = condition.strip().lower()
            if normalized in ("true", "false"):
                return normalized == "true"
            # Simple comparison expressions
            if "==" in condition:
                parts = condition.split("==", 1)
                left = self._get_value(parts[0].strip(), inputs)
                right = self._get_value(parts[1].strip(), inputs)
                return left == right
            elif "!=" in condition:
                parts = condition.split("!=", 1)
                left = self._get_value(parts[0].strip(), inputs)
                right = self._get_value(parts[1].strip(), inputs)
                return left != right
            elif ">" in condition:
                parts = condition.split(">", 1)
                left = self._get_value(parts[0].strip(), inputs)
                right = self._get_value(parts[1].strip(), inputs)
                return float(left) > float(right)
            elif "<" in condition:
                parts = condition.split("<", 1)
                left = self._get_value(parts[0].strip(), inputs)
                right = self._get_value(parts[1].strip(), inputs)
                return float(left) < float(right)
            else:
                # Treat as variable reference
                value = self._get_value(condition, inputs)
                return bool(value)

        # Otherwise, convert to boolean
        return bool(condition)

    def _get_value(self, expr: str, inputs: dict[str, Any]) -> Any:
        """Get value from expression (variable or literal).

        Args:
            expr: Expression string.
            inputs: Input dictionary.

        Returns:
            Value.
        """
        # Remove quotes if present
        expr = expr.strip().strip('"').strip("'")

        # Check if it's a variable reference
        if expr in inputs:
            return inputs[expr]

        # Try to parse as number
        try:
            if "." in expr:
                return float(expr)
            return int(expr)
        except ValueError:
            pass

        normalized = expr.lower()
        if normalized in ("true", "false"):
            return normalized == "true"

        # Return as string
        return expr
