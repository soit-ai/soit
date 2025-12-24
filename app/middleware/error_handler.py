""" error_handler

Global error handler middleware.
"""

from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from fastapi.responses import JSONResponse

from app.kernel.commons.errors import KernelError, error_envelope
from app.kernel.commons.errors import UnauthorizedError, NotFoundError
import logging

logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Middleware to handle errors globally."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and handle errors."""
        try:
            response = await call_next(request)
            return response
        except (KernelError, UnauthorizedError, NotFoundError) as e:
            # Handle KernelError
            logger.error(f"KernelError: {e.code} - {e.message}", exc_info=True)
            
            status_code = 500
            if e.code == "NOT_FOUND":
                status_code = 404
            elif e.code == "FORBIDDEN_ACCESS":
                status_code = 403
            elif e.code == "UNAUTHORIZED":
                status_code = 401
            elif e.code in ("BAD_REQUEST", "DUPLICATE_NAME", "INVALID_PARAMS"):
                status_code = 400
            
            error_response = error_envelope(
                code=e.code,
                message=e.message,
                details=e.details,
                request_id=getattr(request.state, "request_id", None),
            )
            return JSONResponse(
                status_code=status_code,
                content=error_response,
            )
        except Exception as e:
            # Handle unexpected errors
            logger.exception(f"Unexpected error: {str(e)}")
            
            error_response = error_envelope(
                code="INTERNAL_ERROR",
                message="Internal server error",
                request_id=getattr(request.state, "request_id", None),
            )
            return JSONResponse(
                status_code=500,
                content=error_response,
            )

