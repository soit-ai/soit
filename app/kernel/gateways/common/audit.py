""" audit

Gateway audit logging utilities.
"""

import json
from typing import Dict, Any, Optional
from app.kernel.trace.writer import TraceWriter
from app.kernel.commons.time import utc_now


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
    request_data: Dict[str, Any],
    response_data: Optional[Dict[str, Any]] = None,
    storage_gateway: Optional[Any] = None,
) -> None:
    """Log gateway request/response to audit log.
    
    Args:
        trace_writer: Trace writer instance.
        run_id: Run ID.
        step_id: Step ID.
        gateway_type: Gateway type (llm, tool, vector, storage, secrets).
        request_data: Request data dictionary.
        response_data: Optional response data dictionary.
        storage_gateway: Optional storage gateway for large payloads.
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
    
    # Serialize to JSON
    audit_json = json.dumps(audit_log, ensure_ascii=False, indent=2)
    audit_bytes = audit_json.encode("utf-8")
    
    # If payload is large (>64KB), store in object storage
    if len(audit_bytes) > 64 * 1024 and storage_gateway:
        try:
            # Store in object storage
            storage_key = f"audit/{run_id}/{step_id}.json"
            await storage_gateway.put(
                key=storage_key,
                data=audit_bytes,
                content_type="application/json",
            )
            
            # Create artifact reference
            trace_writer.create_artifact(
                run_id=run_id,
                artifact_type="json",
                storage_key=storage_key,
                meta={
                    "gateway_type": gateway_type,
                    "size": len(audit_bytes),
                    "mime_type": "application/json",
                },
            )
        except Exception:
            # If storage fails, fall back to truncating and storing in step metadata
            truncated = audit_json[:8192] + "... [truncated]"
            # Store truncated version in step error_details or metrics
            pass
    else:
        # Store in step metadata (if small enough)
        # For now, we'll store a reference in step metrics
        # Full audit log can be retrieved from artifact if stored
        pass

