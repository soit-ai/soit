"""OpenAPI configuration aligned with middleware-visible wire contracts."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi


def _success_envelope_schema(data_schema: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["success", "code", "message", "data"],
        "properties": {
            "success": {"type": "boolean", "const": True, "default": True},
            "code": {"type": "string", "default": "OK"},
            "message": {"type": "string", "default": "OK"},
            "data": data_schema,
            "request_id": {"type": ["string", "null"]},
            "run_id": {"type": ["string", "null"]},
        },
    }


def install_enveloped_openapi(app: FastAPI) -> None:
    """Make generated success schemas match ResponseEnvelopeMiddleware output."""

    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
            tags=app.openapi_tags,
        )
        for path_item in schema.get("paths", {}).values():
            for operation in path_item.values():
                if not isinstance(operation, dict):
                    continue
                for status_code, response in operation.get("responses", {}).items():
                    if not str(status_code).startswith(("2", "3")):
                        continue
                    json_content = response.get("content", {}).get("application/json")
                    if not json_content:
                        continue
                    data_schema = json_content.get("schema", {})
                    properties = data_schema.get("properties", {})
                    if {"success", "code", "message"}.issubset(properties):
                        continue
                    json_content["schema"] = _success_envelope_schema(data_schema)
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi


tags_metadata = [
    {"name": "identity", "description": "Identity, tenant, workspace, and access management endpoints."},
    {"name": "workflows", "description": "Workflow management and execution endpoints."},
    {"name": "knowledge", "description": "Knowledge base lifecycle and retrieval observe endpoints."},
    {"name": "runs", "description": "Run history and cost summary endpoints."},
    {"name": "tasks", "description": "Background task control and runtime task inspection endpoints."},
    {"name": "threads", "description": "Thread lifecycle and message history endpoints."},
    {"name": "modelhub", "description": "Model registry and provider synchronization endpoints."},
    {"name": "plugins", "description": "Plugin marketplace, installation, and registry endpoints."},
    {"name": "observe", "description": "Approval, feedback, replay, and governance inspection endpoints."},
    {"name": "security", "description": "Security and policy management endpoints."},
    {"name": "secrets", "description": "Workspace secrets management endpoints."},
    {"name": "agents", "description": "Agent runtime endpoints."},
    {"name": "notifications", "description": "Notification inbox and delivery endpoints."},
    {"name": "api_keys", "description": "API key lifecycle endpoints."},
    {"name": "health", "description": "Health check and monitoring endpoints."},
]
