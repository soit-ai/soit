""" audit

Gateway audit logging utilities.
"""

import json
from typing import Any

from app.kernel.commons.time import utc_now
from app.kernel.runtime.runs.writer import TraceWriter


def filter_sensitive_data(data: Any) -> Any:
    """Filter sensitive information from audit data.

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
            if key_lower in {"secret_ref", "signing_policy_ref"}:
                filtered[key] = filter_sensitive_data(value)
                continue
            if isinstance(value, dict) and "secret_ref" in value:
                filtered[key] = filter_sensitive_data(value)
                continue
            if isinstance(value, list) and any(isinstance(item, dict) and "secret_ref" in item for item in value):
                filtered[key] = filter_sensitive_data(value)
                continue
            sensitive_fields = {
                "password", "secret", "token", "api_key", "apikey",
                "authorization", "auth", "credential", "private_key",
                "privatekey", "access_token", "refresh_token",
            }
            is_sensitive = any(sensitive in key_lower for sensitive in sensitive_fields)

            if is_sensitive:
                filtered[key] = "***REDACTED***"
            else:
                filtered[key] = filter_sensitive_data(value)
        return filtered
    elif isinstance(data, list):
        return [filter_sensitive_data(item) for item in data]
    else:
        return data


async def log_gateway_request(
    trace_writer: TraceWriter,
    run_id: str,
    step_id: str,
    gateway_type: str,
    request_data: dict[str, Any],
    response_data: dict[str, Any] | None = None,
    storage_port: Any | None = None,
) -> None:
    """Log gateway request/response to audit log.

    Args:
        trace_writer: Trace writer instance.
        run_id: Run ID.
        step_id: Step ID.
        gateway_type: Gateway type (llm, tool, vector, storage, secrets).
        request_data: Request data dictionary.
        response_data: Optional response data dictionary.
        storage_port: Optional storage gateway for large payloads.
    """
    if not trace_writer:
        return

    # Filter sensitive data
    filtered_request = filter_sensitive_data(request_data)
    filtered_response = filter_sensitive_data(response_data) if response_data else None

    # Prepare audit log
    audit_log = {
        "gateway_type": gateway_type,
        "request": filtered_request,
        "response": filtered_response,
        "timestamp": str(utc_now()),
    }

    audit_json = json.dumps(audit_log, ensure_ascii=True, default=str, separators=(",", ":"))
    audit_bytes = audit_json.encode("utf-8")
    inline_limit = 8 * 1024

    if len(audit_bytes) <= inline_limit:
        trace_writer.update_step_metrics(
            step_id,
            {
                "audit_json": audit_json,
                "audit_size": len(audit_bytes),
            },
        )
        return

    if storage_port:
        try:
            storage_key = f"audit/{run_id}/{step_id}.json"
            await storage_port.put(
                key=storage_key,
                data=audit_bytes,
                content_type="application/json",
                run_id=run_id,
            )
            trace_writer.create_artifact(
                run_id=run_id,
                artifact_type="json",
                storage_key=storage_key,
                step_id=step_id,
                mime="application/json",
                size_bytes=len(audit_bytes),
                meta={
                    "gateway_type": gateway_type,
                    "size": len(audit_bytes),
                    "mime_type": "application/json",
                },
            )
            trace_writer.update_step_metrics(
                step_id,
                {
                    "audit_artifact": storage_key,
                    "audit_size": len(audit_bytes),
                },
            )
            return
        except Exception:
            # Fall back to inline preview
            pass

    preview = audit_json[:inline_limit]
    trace_writer.update_step_metrics(
        step_id,
        {
            "audit_preview": preview,
            "audit_truncated": True,
            "audit_size": len(audit_bytes),
        },
    )
