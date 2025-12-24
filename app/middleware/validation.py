""" validation

Request validation middleware.
"""

from typing import Callable, Any
from fastapi import Request, HTTPException, status
from fastapi.routing import APIRoute

from app.kernel.specs.validator import SpecValidator


class ValidationMiddleware:
    """Middleware for request validation."""
    
    def __init__(self, app):
        """Initialize validation middleware.
        
        Args:
            app: FastAPI application instance.
        """
        self.app = app
        self.validator = SpecValidator()
    
    async def __call__(self, scope, receive, send):
        """Process request.
        
        Args:
            scope: ASGI scope.
            receive: ASGI receive callable.
            send: ASGI send callable.
        """
        if scope["type"] == "http":
            request = Request(scope, receive)
            
            # Check if request body contains spec fields that need validation
            # This is typically handled by Pydantic models, but we can add
            # additional JSON Schema validation here if needed
            
            # For now, pass through - validation is handled by Pydantic models
            pass
        
        await self.app(scope, receive, send)


def validate_spec(spec_type: str, spec_data: dict) -> None:
    """Validate a spec against JSON Schema.
    
    Args:
        spec_type: Spec type (e.g., "workflow", "plugin").
        spec_data: Spec data dictionary.
        
    Raises:
        HTTPException: If validation fails.
    """
    validator = SpecValidator()
    try:
        validator.validate(spec(spec_type, spec_data))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Spec validation failed: {str(e)}",
        )

