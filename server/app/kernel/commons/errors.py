"""Kernel error types."""

from typing import Any


class KernelError(Exception):
    """Base exception for kernel errors."""

    def __init__(
        self,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
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

    def __init__(self, message: str = "Unauthorized", details: dict[str, Any] | None = None):
        super().__init__("UNAUTHORIZED", message, details)


class ForbiddenError(KernelError):
    """Access forbidden (insufficient permissions)."""

    def __init__(self, message: str = "Forbidden", details: dict[str, Any] | None = None):
        super().__init__("FORBIDDEN", message, details)


class NotFoundError(KernelError):
    """Resource not found."""

    def __init__(self, message: str = "Not found", details: dict[str, Any] | None = None):
        super().__init__("NOT_FOUND", message, details)


class ValidationError(KernelError):
    """Validation failed."""

    def __init__(self, message: str = "Validation failed", details: dict[str, Any] | None = None):
        super().__init__("VALIDATION_ERROR", message, details)


class ConflictError(KernelError):
    """Resource conflict (e.g., duplicate)."""

    def __init__(self, message: str = "Conflict", details: dict[str, Any] | None = None):
        super().__init__("CONFLICT", message, details)


class TimeoutError(KernelError):
    """Operation timeout."""

    def __init__(self, message: str = "Operation timeout", details: dict[str, Any] | None = None):
        super().__init__("TIMEOUT", message, details)


class CreditExhaustedError(KernelError):
    """Workspace credit balance is exhausted; metered invocations are blocked."""

    def __init__(
        self,
        message: str = "Workspace credit balance exhausted",
        details: dict[str, Any] | None = None,
    ):
        super().__init__("CREDIT_EXHAUSTED", message, details)


# Codes whose messages describe workspace configuration the caller can fix
# (model routing, credit) rather than runtime internals. Only these messages
# may be shown to end users verbatim; everything else stays masked.
_PUBLIC_SAFE_ERROR_CODE_PREFIXES = ("MODEL_",)
_PUBLIC_SAFE_ERROR_CODES = frozenset({"CREDIT_EXHAUSTED"})


def public_error_message(error: BaseException, default: str) -> str:
    """Return a user-facing message for an execution failure.

    Configuration-class ``KernelError`` messages are appended to ``default`` so
    users can self-serve (e.g. switch to a model that supports chat); any other
    error keeps the masked ``default`` message.
    """
    if isinstance(error, KernelError):
        code = error.code or ""
        if code in _PUBLIC_SAFE_ERROR_CODES or code.startswith(
            _PUBLIC_SAFE_ERROR_CODE_PREFIXES
        ):
            return f"{default}: {error.message}"
    return default
