""" validator

Validate spec JSON against JSON Schema.
"""

import json
from typing import Dict, Any, Optional, List
from jsonschema import validate, ValidationError as JSONSchemaValidationError
from jsonschema.exceptions import SchemaError

from app.kernel.specs.loader import load_schema
from app.kernel.commons.errors import ValidationError


class SpecValidator:
    """JSON Schema validator for specs."""
    
    def validate(
        self,
        spec_name: str,
        spec_data: Dict[str, Any],
        raise_on_error: bool = True,
    ) -> tuple[bool, Optional[str]]:
        """Validate spec data against schema.
        
        Args:
            spec_name: Schema name (e.g., "workflow_spec").
            spec_data: Spec data to validate.
            raise_on_error: Whether to raise exception on error.
            
        Returns:
            Tuple of (is_valid, error_message).
            
        Raises:
            ValidationError: If validation fails and raise_on_error is True.
        """
        try:
            schema = load_schema(spec_name)
            validate(instance=spec_data, schema=schema)
            return True, None
        except FileNotFoundError as e:
            error_msg = f"Schema not found: {spec_name}"
            if raise_on_error:
                raise ValidationError(error_msg) from e
            return False, error_msg
        except JSONSchemaValidationError as e:
            error_msg = self._format_validation_error(e)
            if raise_on_error:
                raise ValidationError(error_msg, details={"path": list(e.path)}) from e
            return False, error_msg
        except SchemaError as e:
            error_msg = f"Invalid schema: {str(e)}"
            if raise_on_error:
                raise ValidationError(error_msg) from e
            return False, error_msg
    
    def _format_validation_error(self, error: JSONSchemaValidationError) -> str:
        """Format validation error message.
        
        Args:
            error: Validation error.
            
        Returns:
            Formatted error message.
        """
        path = ".".join(str(p) for p in error.path) if error.path else "root"
        return f"Validation failed at {path}: {error.message}"
    
    def validate_workflow_spec(self, spec_data: Dict[str, Any]) -> None:
        """Validate workflow spec.
        
        Args:
            spec_data: Workflow spec data.
            
        Raises:
            ValidationError: If validation fails.
        """
        self.validate("workflow_spec", spec_data, raise_on_error=True)
    
    def validate_tool_spec(self, spec_data: Dict[str, Any]) -> None:
        """Validate tool spec.
        
        Args:
            spec_data: Tool spec data.
            
        Raises:
            ValidationError: If validation fails.
        """
        self.validate("tool_spec", spec_data, raise_on_error=True)
    
    def validate_plugin_spec(self, spec_data: Dict[str, Any]) -> None:
        """Validate plugin spec.
        
        Args:
            spec_data: Plugin spec data.
            
        Raises:
            ValidationError: If validation fails.
        """
        self.validate("plugin_spec", spec_data, raise_on_error=True)
    
    def validate_app_spec(self, spec_data: Dict[str, Any]) -> None:
        """Validate app spec.
        
        Args:
            spec_data: App spec data.
            
        Raises:
            ValidationError: If validation fails.
        """
        self.validate("app_spec", spec_data, raise_on_error=True)


# Global validator instance
validator = SpecValidator()
