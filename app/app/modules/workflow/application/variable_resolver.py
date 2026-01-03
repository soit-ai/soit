""" variable_resolver

Variable resolver for template syntax ({{ inputs.xxx }} and {{ steps.xxx.output.xxx }}).
"""

import re
from typing import Dict, Any, Optional, Union
from app.kernel.commons.errors import ValidationError


class VariableResolver:
    """Resolve template variables in workflow node inputs."""
    
    # Pattern: {{ inputs.field }} or {{ steps.node_id.output.field }}
    VARIABLE_PATTERN = re.compile(r'\{\{\s*(\w+)\.([\w.]+)\s*\}\}')
    
    def __init__(self, inputs: Dict[str, Any], steps_outputs: Optional[Dict[str, Dict[str, Any]]] = None):
        """Initialize variable resolver.
        
        Args:
            inputs: Workflow inputs dictionary.
            steps_outputs: Dictionary mapping step_id to output data.
        """
        self.inputs = inputs
        self.steps_outputs = steps_outputs or {}
    
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
    
    def _resolve_string(self, template: str) -> str:
        """Resolve variables in string template.
        
        Args:
            template: String template with variables.
            
        Returns:
            Resolved string.
        """
        def replace_var(match):
            prefix = match.group(1)
            path = match.group(2)
            
            if prefix == "inputs":
                value = self._get_nested_value(self.inputs, path)
            elif prefix == "steps":
                # Parse steps.node_id.output.field
                parts = path.split(".", 2)
                if len(parts) < 3 or parts[1] != "output":
                    raise ValidationError(f"Invalid steps variable: {path}")
                step_id = parts[0]
                field_path = parts[2] if len(parts) > 2 else None
                
                step_output = self.steps_outputs.get(step_id)
                if step_output is None:
                    raise ValidationError(f"Step output not found: {step_id}")
                
                if field_path:
                    value = self._get_nested_value(step_output, field_path)
                else:
                    value = step_output
            else:
                raise ValidationError(f"Unknown variable prefix: {prefix}")
            
            if value is None:
                raise ValidationError(f"Variable not found: {prefix}.{path}")
            
            # Convert to string for substitution
            if isinstance(value, (dict, list)):
                return str(value)
            return str(value)
        
        return self.VARIABLE_PATTERN.sub(replace_var, template)
    
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
            variables.extend([f"{prefix}.{path}" for prefix, path in matches])
        elif isinstance(template, dict):
            for value in template.values():
                variables.extend(cls.extract_variables(value))
        elif isinstance(template, list):
            for item in template:
                variables.extend(cls.extract_variables(item))
        
        return list(set(variables))  # Remove duplicates

