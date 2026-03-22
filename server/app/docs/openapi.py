""" openapi

OpenAPI configuration and customization.
"""

from typing import Dict, Any


def custom_openapi() -> Dict[str, Any]:
    """Generate custom OpenAPI schema.
    
    Returns:
        OpenAPI schema dictionary.
    """
    # This function can be used to customize the OpenAPI schema
    # For now, FastAPI's automatic generation is sufficient
    # But we can add custom tags, descriptions, examples, etc. here
    return {}


# OpenAPI tags for API grouping
tags_metadata = [
    {
        "name": "identity",
        "description": "Identity, tenant, workspace, and access management endpoints.",
    },
    {
        "name": "workflows",
        "description": "Workflow management and execution endpoints.",
    },
    {
        "name": "knowledge",
        "description": "Knowledge base lifecycle and retrieval observability endpoints.",
    },
    {
        "name": "runs",
        "description": "Run history and cost summary endpoints.",
    },
    {
        "name": "tasks",
        "description": "Background task control and runtime task inspection endpoints.",
    },
    {
        "name": "threads",
        "description": "Thread lifecycle and message history endpoints.",
    },
    {
        "name": "memory",
        "description": "Memory storage and retrieval endpoints.",
    },
    {
        "name": "modelhub",
        "description": "Model registry and provider synchronization endpoints.",
    },
    {
        "name": "plugins",
        "description": "Plugin marketplace, installation, and registry endpoints.",
    },
    {
        "name": "skills",
        "description": "Skill definition, versioning, and publish endpoints.",
    },
    {
        "name": "mcp",
        "description": "MCP server registration and capability catalog endpoints.",
    },
    {
        "name": "observability",
        "description": "Approval, feedback, replay, and governance inspection endpoints.",
    },
    {
        "name": "security",
        "description": "Security and policy management endpoints.",
    },
    {
        "name": "secrets",
        "description": "Workspace secrets management endpoints.",
    },
    {
        "name": "agents",
        "description": "Agent runtime endpoints.",
    },
    {
        "name": "notifications",
        "description": "Notification inbox and delivery endpoints.",
    },
    {
        "name": "websocket",
        "description": "WebSocket endpoints for real-time updates.",
    },
    {
        "name": "api_keys",
        "description": "API key lifecycle endpoints.",
    },
    {
        "name": "sse",
        "description": "Server-Sent Events endpoints for streaming.",
    },
    {
        "name": "health",
        "description": "Health check and monitoring endpoints.",
    },
]
