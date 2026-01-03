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
        "name": "websocket",
        "description": "WebSocket endpoints for real-time updates.",
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

