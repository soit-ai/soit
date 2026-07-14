""" request_id

Request ID middleware for tracking requests.
"""

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Middleware to add request ID to requests and responses."""

    async def dispatch(self, request: Request, call_next):
        """Process request and add request Id."""
        # Get or generate request ID
        request_id = request.headers.get("X-Request-Id")
        if not request_id:
            request_id = str(uuid.uuid4())

        # Add request ID to request state
        request.state.request_id = request_id

        # Process request
        response = await call_next(request)

        # Add request ID to response headers
        response.headers["X-Request-Id"] = request_id

        return response

