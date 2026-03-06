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
        "name": "workflows",
        "description": "Workflow management and execution endpoints.",
    },
    {
        "name": "datasets",
        "description": "Dataset and knowledge base management endpoints.",
    },
    {
        "name": "chat",
        "description": "Chat completion and conversation endpoints.",
    },
    {
        "name": "runs",
        "description": "Run history and cost summary endpoints.",
    },
    {
        "name": "bots",
        "description": "Bot definition and execution endpoints.",
    },
    {
        "name": "memory",
        "description": "Memory storage and retrieval endpoints.",
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
        "name": "appcenter",
        "description": "App center management and marketplace endpoints.",
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
