""" variable_resolver

Variable resolver for template syntax ({{ inputs }}, {{ context }}, {{ steps.node.output.xxx }}).
"""

import re
from typing import Dict, Any, Optional, Union, List, Set
from app.kernel.commons.errors import ValidationError


class VariableResolver:
    """Resolve template variables in workflow node inputs."""
    
    # Pattern: {{ inputs }} or {{ inputs.field }} or {{ steps.node_id.output.field }}
    VARIABLE_PATTERN = re.compile(r'\{\{\s*(\w+)(?:\.([\w.]+))?\s*\}\}')
    
    def __init__(
        self,
        inputs: Dict[str, Any],
        steps_outputs: Optional[Dict[str, Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None,
        skipped_steps: Optional[Set[str]] = None,
    ):
        """Initialize variable resolver.
        
        Args:
            inputs: Workflow inputs dictionary.
            steps_outputs: Dictionary mapping step_id to output data.
            context: Optional context dictionary (tenant/workspace/user info, etc.).
            skipped_steps: Optional set of skipped step IDs.
        """
        self.inputs = inputs
        self.steps_outputs = steps_outputs or {}
        self.context = context or {}
        self.skipped_steps = skipped_steps or set()
    
    def resolve(self, template: Union[str, Dict[str, Any], list]) -> Any:
        """Resolve variables in template.
        
        Args:
            template: Template string, dict, or list that may contain variables.
            
        Returns:
            Resolved value with variables substituted.
        """
        if isinstance(template, str):
            return self._resolve_string(template)
        elif isinstance(template, dict):
            return {k: self.resolve(v) for k, v in template.items()}
        elif isinstance(template, list):
            return [self.resolve(item) for item in template]
        else:
            return template
    
    def _resolve_string(self, template: str) -> Any:
        """Resolve variables in string template.
        
        Args:
            template: String template with variables.
            
        Returns:
            Resolved value.
        """
        full_match = self.VARIABLE_PATTERN.fullmatch(template.strip())

        def replace_var(match):
            prefix = match.group(1)
            path = match.group(2)
            
            if prefix == "inputs":
                if not path:
                    value = self.inputs
                else:
                    value = self._get_nested_value(self.inputs, path)
            elif prefix == "context":
                if not path:
                    value = self.context
                else:
                    value = self._get_nested_value(self.context, path)
            elif prefix == "steps":
                if not path:
                    value = self.steps_outputs
                else:
                    # Parse steps.node_id.output.field
                    parts = path.split(".", 2)
                    if len(parts) < 2 or parts[1] != "output":
                        raise ValidationError(f"Invalid steps variable: {path}")
                    step_id = parts[0]
                    field_path = parts[2] if len(parts) > 2 else None
                
                    step_output = self.steps_outputs.get(step_id)
                    if step_output is None:
                        if step_id in self.skipped_steps:
                            value = None
                        else:
                            raise ValidationError(f"Step output not found: {step_id}")
                    else:
                        if field_path:
                            value = self._get_nested_value(step_output, field_path)
                        else:
                            value = step_output
            else:
                raise ValidationError(f"Unknown variable prefix: {prefix}")
            
            if value is None and not (prefix == "steps" and path and path.split(".", 1)[0] in self.skipped_steps):
                raise ValidationError(f"Variable not found: {prefix}.{path or ''}".rstrip("."))
            
            # Convert to string for substitution
            if value is None:
                return ""
            if isinstance(value, (dict, list)):
                return str(value)
            return str(value)

        if full_match:
            prefix = full_match.group(1)
            path = full_match.group(2)
            return self._resolve_value(prefix, path)

        return self.VARIABLE_PATTERN.sub(replace_var, template)

    def _resolve_value(self, prefix: str, path: Optional[str]) -> Any:
        """Resolve a variable to its raw value."""
        if prefix == "inputs":
            if not path:
                return self.inputs
            value = self._get_nested_value(self.inputs, path)
            if value is None:
                raise ValidationError(f"Variable not found: inputs.{path}")
            return value
        if prefix == "context":
            if not path:
                return self.context
            value = self._get_nested_value(self.context, path)
            if value is None:
                raise ValidationError(f"Variable not found: context.{path}")
            return value
        if prefix == "steps":
            if not path:
                return self.steps_outputs
            parts = path.split(".", 2)
            if len(parts) < 2 or parts[1] != "output":
                raise ValidationError(f"Invalid steps variable: {path}")
            step_id = parts[0]
            field_path = parts[2] if len(parts) > 2 else None
            step_output = self.steps_outputs.get(step_id)
            if step_output is None:
                if step_id in self.skipped_steps:
                    return None
                raise ValidationError(f"Step output not found: {step_id}")
            if field_path:
                value = self._get_nested_value(step_output, field_path)
                if value is None:
                    raise ValidationError(f"Variable not found: steps.{path}")
                return value
            return step_output
        raise ValidationError(f"Unknown variable prefix: {prefix}")
    
    def _get_nested_value(self, obj: Any, path: str) -> Any:
        """Get nested value from object using dot notation.
        
        Args:
            obj: Object to get value from.
            path: Dot-separated path (e.g., "field.subfield").
            
        Returns:
            Value at path, or None if not found.
        """
        if not isinstance(obj, dict):
            return None
        
        parts = path.split(".")
        current = obj
        
        for part in parts:
            if not isinstance(current, dict):
                return None
            current = current.get(part)
            if current is None:
                return None
        
        return current
    
    @classmethod
    def extract_variables(cls, template: Union[str, Dict[str, Any], list]) -> List[str]:
        """Extract all variable references from template.
        
        Args:
            template: Template to extract variables from.
            
        Returns:
            List of variable references (e.g., ["inputs.query", "steps.r1.output.context"]).
        """
        variables = []
        
        if isinstance(template, str):
            matches = cls.VARIABLE_PATTERN.findall(template)
            for prefix, path in matches:
                if path:
                    variables.append(f"{prefix}.{path}")
                else:
                    variables.append(prefix)
        elif isinstance(template, dict):
            for value in template.values():
                variables.extend(cls.extract_variables(value))
        elif isinstance(template, list):
            for item in template:
                variables.extend(cls.extract_variables(item))
        
        return list(set(variables))  # Remove duplicates

