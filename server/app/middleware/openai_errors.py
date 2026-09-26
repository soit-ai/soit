"""Error bodies for the OpenAI-compatible surface.

Routes under ``/v1`` answer OpenAI SDK clients, which parse failures from
``{"error": {"message", "type", "param", "code"}}`` and decide what to retry
from the status code and ``type``. Every other route keeps the SOIT envelope.
One function builds either shape from the same status, code and message, so
the exception handlers and the error middleware cannot disagree.
"""

from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse

OPENAI_COMPATIBLE_PREFIX = "/v1"

_TYPE_BY_STATUS: dict[int, str] = {
    400: "invalid_request_error",
    401: "authentication_error",
    402: "insufficient_quota",
    403: "permission_error",
    404: "invalid_request_error",
    409: "invalid_request_error",
    413: "invalid_request_error",
    422: "invalid_request_error",
    429: "rate_limit_error",
}


def is_openai_compatible_path(path: str) -> bool:
    """Whether ``path`` belongs to the OpenAI-compatible surface."""

    return path == OPENAI_COMPATIBLE_PREFIX or path.startswith(OPENAI_COMPATIBLE_PREFIX + "/")


def openai_error_type(status_code: int) -> str:
    if status_code in _TYPE_BY_STATUS:
        return _TYPE_BY_STATUS[status_code]
    return "api_error" if status_code >= 500 else "invalid_request_error"


def _param_from(details: dict[str, Any] | None) -> str | None:
    if not details:
        return None
    errors = details.get("errors")
    if isinstance(errors, list) and errors and isinstance(errors[0], dict):
        field = str(errors[0].get("field") or "")
        # FastAPI prefixes body fields with "body."; OpenAI names the field.
        return field.removeprefix("body.") or None
    param = details.get("param")
    return str(param) if param else None


def openai_error_body(
    status_code: int,
    *,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "error": {
            "message": message,
            "type": openai_error_type(status_code),
            "param": _param_from(details),
            "code": code.lower(),
        }
    }


def retry_after_headers(code: str, details: dict[str, Any] | None) -> dict[str, str] | None:
    """`Retry-After` for a refused call that says when to come back."""

    if code != "RATE_LIMIT_EXCEEDED" or not details:
        return None
    retry_after = details.get("retry_after")
    if isinstance(retry_after, int | float) and retry_after > 0:
        return {"Retry-After": str(int(retry_after))}
    return None


def error_response(
    path: str,
    status_code: int,
    envelope: dict[str, Any],
    *,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Answer with the SOIT envelope, or the OpenAI body under ``/v1``."""

    if is_openai_compatible_path(path):
        content = openai_error_body(
            status_code,
            code=str(envelope.get("code") or "error"),
            message=str(envelope.get("message") or ""),
            details=envelope.get("details") if isinstance(envelope.get("details"), dict) else None,
        )
        return JSONResponse(status_code=status_code, content=content, headers=headers)
    return JSONResponse(status_code=status_code, content=envelope, headers=headers)
