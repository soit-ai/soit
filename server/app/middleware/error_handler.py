""" error_handler

Global error handler middleware.
"""

import logging
import re
from collections.abc import Callable
from typing import Any

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.kernel.commons.errors import (
    KernelError,
)
from app.kernel.observe.context import get_log_context
from app.middleware.response_envelope import error_envelope

logger = logging.getLogger(__name__)

# Error code to HTTP status code mapping
ERROR_CODE_TO_STATUS: dict[str, int] = {
    "UNAUTHORIZED": 401,
    "FORBIDDEN": 403,
    "NOT_FOUND": 404,
    "VALIDATION_ERROR": 400,
    "CONFLICT": 409,
    "TIMEOUT": 504,
    "BAD_REQUEST": 400,
    "DUPLICATE_NAME": 409,
    "INVALID_PARAMS": 400,
    "INVALID_SOURCE_URI": 400,
    "CRAWLER_EMPTY_CONTENT": 422,
    "CRAWLER_CONTENT_TOO_LARGE": 413,
    "CRAWLER_FETCH_FAILED": 502,
    "RATE_LIMIT_EXCEEDED": 429,
    "INTERNAL_ERROR": 500,
    "SERVICE_UNAVAILABLE": 503,
}

# Sensitive fields to filter from error details
SENSITIVE_FIELDS = {
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "auth",
    "credential",
    "private_key",
    "privatekey",
}


def filter_sensitive_data(data: Any) -> Any:
    """Filter sensitive information from error details.

    Args:
        data: Data to filter (dict, list, or primitive).

    Returns:
        Filtered data.
    """
    if isinstance(data, dict):
        filtered = {}
        for key, value in data.items():
            # Check if key contains sensitive field name
            key_lower = key.lower()
            is_sensitive = any(sensitive in key_lower for sensitive in SENSITIVE_FIELDS)

            if is_sensitive:
                filtered[key] = "***REDACTED***"
            else:
                filtered[key] = filter_sensitive_data(value)
        return filtered
    elif isinstance(data, list):
        return [filter_sensitive_data(item) for item in data]
    else:
        return data


def sanitize_error_message(message: str) -> str:
    """Sanitize error message to remove sensitive information.

    Args:
        message: Error message string.

    Returns:
        Sanitized message.
    """
    # Remove potential API keys, tokens, etc. from message
    # Pattern: looks like tokens/keys (long alphanumeric strings)
    sanitized = re.sub(
        r'\b[A-Za-z0-9]{32,}\b',
        '***REDACTED***',
        message
    )
    return sanitized


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Middleware to handle errors globally with enhanced error handling."""

    def _resolve_trace_ids(self, request: Request) -> tuple[str | None, str | None]:
        log_ctx = get_log_context()
        request_id = getattr(request.state, "request_id", None) or log_ctx.get("request_id")
        run_id = getattr(request.state, "run_id", None) or log_ctx.get("run_id")
        return request_id, run_id

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and handle errors."""
        try:
            response = await call_next(request)
            return response
        except KernelError as e:
            # Handle KernelError and its subclasses
            logger.error(
                f"KernelError: {e.code} - {e.message}",
                exc_info=True,
                extra={
                    "error_code": e.code,
                    "request_id": getattr(request.state, "request_id", None),
                }
            )

            # Get status code from mapping
            status_code = ERROR_CODE_TO_STATUS.get(e.code, 500)

            # Filter sensitive data from details
            filtered_details = filter_sensitive_data(e.details) if e.details else {}

            # Sanitize error message
            sanitized_message = sanitize_error_message(e.message)

            request_id, run_id = self._resolve_trace_ids(request)
            error_response = error_envelope(
                code=e.code,
                message=sanitized_message,
                details=filtered_details,
                request_id=request_id,
                run_id=run_id,
            )
            return JSONResponse(
                status_code=status_code,
                content=error_response,
            )
        except RequestValidationError as e:
            # Handle FastAPI validation errors
            logger.warning(
                f"Validation error: {str(e)}",
                extra={
                    "request_id": getattr(request.state, "request_id", None),
                }
            )

            # Extract validation errors
            errors = []
            for error in e.errors():
                errors.append({
                    "field": ".".join(str(loc) for loc in error.get("loc", [])),
                    "message": error.get("msg", "Validation error"),
                    "type": error.get("type", "validation_error"),
                })

            request_id, run_id = self._resolve_trace_ids(request)
            error_response = error_envelope(
                code="VALIDATION_ERROR",
                message="Request validation failed",
                details={"errors": errors},
                request_id=request_id,
                run_id=run_id,
            )
            return JSONResponse(
                status_code=400,
                content=error_response,
            )
        except StarletteHTTPException as e:
            # Handle Starlette HTTP exceptions
            logger.warning(
                f"HTTPException: {e.status_code} - {e.detail}",
                extra={
                    "status_code": e.status_code,
                    "request_id": getattr(request.state, "request_id", None),
                }
            )

            # Map status code to error code
            status_to_code = {
                400: "BAD_REQUEST",
                401: "UNAUTHORIZED",
                403: "FORBIDDEN",
                404: "NOT_FOUND",
                409: "CONFLICT",
                429: "RATE_LIMIT_EXCEEDED",
                500: "INTERNAL_ERROR",
                503: "SERVICE_UNAVAILABLE",
            }
            error_code = status_to_code.get(e.status_code, "HTTP_ERROR")

            request_id, run_id = self._resolve_trace_ids(request)
            error_response = error_envelope(
                code=error_code,
                message=str(e.detail) if e.detail else f"HTTP {e.status_code}",
                request_id=request_id,
                run_id=run_id,
            )
            return JSONResponse(
                status_code=e.status_code,
                content=error_response,
            )
        except Exception as e:
            # Handle unexpected errors
            logger.exception(
                f"Unexpected error: {str(e)}",
                extra={
                    "request_id": getattr(request.state, "request_id", None),
                    "error_type": type(e).__name__,
                }
            )

            # In production, don't expose internal error details
            error_message = "Internal server error"
            error_details: dict[str, Any] | None = None

            # In development, include more details
            import os
            if os.getenv("ENVIRONMENT", "production").lower() == "development":
                error_message = f"Internal server error: {str(e)}"
                error_details = {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                }

            request_id, run_id = self._resolve_trace_ids(request)
            error_response = error_envelope(
                code="INTERNAL_ERROR",
                message=error_message,
                details=error_details,
                request_id=request_id,
                run_id=run_id,
            )
            return JSONResponse(
                status_code=500,
                content=error_response,
            )
