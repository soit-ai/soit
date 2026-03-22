""" errors

Kernel error types and error envelope helpers.
"""

from typing import Any, Dict, Optional


class KernelError(Exception):
    """Base exception for kernel errors."""
    
    def __init__(
        self,
        code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Initialize kernel error.
        
        Args:
            code: Error code (e.g., "UNAUTHORIZED", "NOT_FOUND").
            message: Human-readable error message.
            details: Optional additional error details.
        """
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class UnauthorizedError(KernelError):
    """Authentication or authorization failed."""
    
    def __init__(self, message: str = "Unauthorized", details: Optional[Dict[str, Any]] = None):
        super().__init__("UNAUTHORIZED", message, details)


class ForbiddenError(KernelError):
    """Access forbidden (insufficient permissions)."""
    
    def __init__(self, message: str = "Forbidden", details: Optional[Dict[str, Any]] = None):
        super().__init__("FORBIDDEN", message, details)


class NotFoundError(KernelError):
    """Resource not found."""
    
    def __init__(self, message: str = "Not found", details: Optional[Dict[str, Any]] = None):
        super().__init__("NOT_FOUND", message, details)


class ValidationError(KernelError):
    """Validation failed."""
    
    def __init__(self, message: str = "Validation failed", details: Optional[Dict[str, Any]] = None):
        super().__init__("VALIDATION_ERROR", message, details)


class ConflictError(KernelError):
    """Resource conflict (e.g., duplicate)."""
    
    def __init__(self, message: str = "Conflict", details: Optional[Dict[str, Any]] = None):
        super().__init__("CONFLICT", message, details)


class TimeoutError(KernelError):
    """Operation timeout."""
    
    def __init__(self, message: str = "Operation timeout", details: Optional[Dict[str, Any]] = None):
        super().__init__("TIMEOUT", message, details)


def error_envelope(
    code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Create error envelope according to API conventions.
    
    Args:
        code: Error code.
        message: Human-readable message.
        details: Optional additional details.
        request_id: Optional request ID for tracing.
        run_id: Optional run ID for tracing.
        
    Returns:
        Error envelope dictionary.
    """
    envelope: Dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        }
    }
    if request_id:
        envelope["request_id"] = request_id
    if run_id:
        envelope["run_id"] = run_id
    return envelope
