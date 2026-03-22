"""response

Standard API response envelopes.
"""

from typing import Any, Dict, Optional


def success_envelope(
    *,
    data: Any,
    message: str = "OK",
    code: str = "OK",
    request_id: Optional[str] = None,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a standard success envelope."""
    payload: Dict[str, Any] = {
        "success": True,
        "code": code,
        "message": message,
        "data": data,
    }
    if request_id:
        payload["request_id"] = request_id
    if run_id:
        payload["run_id"] = run_id
    return payload


def error_envelope(
    *,
    code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a standard error envelope."""
    detail_payload = details or {}
    payload: Dict[str, Any] = {
        "success": False,
        "code": code,
        "message": message,
        "details": detail_payload,
    }
    if request_id:
        payload["request_id"] = request_id
    if run_id:
        payload["run_id"] = run_id
    return payload


def is_enveloped(payload: Any) -> bool:
    """Check if payload already matches the standard envelope shape."""
    if not isinstance(payload, dict):
        return False
    if {"success", "code", "message"}.issubset(payload.keys()):
        return True
    error = payload.get("error")
    if isinstance(error, dict) and {"code", "message"}.issubset(error.keys()):
        return True
    return False
