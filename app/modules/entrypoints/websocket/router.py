""" router

WebSocket API routes (FastAPI).
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from fastapi.security import HTTPBearer

from app.kernel.contracts.context import RequestContext
from app.kernel.commons.ids import generate_ulid
from app.middleware.auth import get_current_context_from_request
from app.modules.entrypoints.websocket.handlers import WebSocketHandlers


router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = None,
    x_workspace_id: str = None,
):
    """WebSocket endpoint for real-time updates.
    
    Args:
        websocket: WebSocket instance.
        token: Optional JWT token (from query parameter).
        x_workspace_id: Optional workspace ID (from query parameter).
    """
    try:
        # Extract token from query or header
        if not token:
            # Try to get from query parameter
            query_params = dict(websocket.query_params)
            token = query_params.get("token")
            
            # Try to get from Authorization header
            if not token:
                auth_header = websocket.headers.get("Authorization", "")
                if auth_header.startswith("Bearer "):
                    token = auth_header[7:]
        
        if not token:
            await websocket.close(code=1008, reason="Authentication required")
            return
        
        # Get workspace ID from query or header
        if not x_workspace_id:
            query_params = dict(websocket.query_params)
            x_workspace_id = query_params.get("workspace_id")
            if not x_workspace_id:
                x_workspace_id = websocket.headers.get("X-Workspace-Id")
        
        # Resolve context from token
        from app.kernel.identity.context_resolver import ContextResolver
        from app.kernel.identity.auth import JWTManager
        from app.kernel.config.settings import settings
        
        jwt_manager = JWTManager(
            secret_key=settings.secret_key,
            algorithm=settings.jwt_algorithm,
        )
        resolver = ContextResolver(jwt_manager)
        
        try:
            ctx = await resolver.resolve_from_token(token, x_workspace_id)
        except Exception as e:
            await websocket.close(code=1008, reason=f"Authentication failed: {str(e)}")
            return
        
        # Generate connection ID
        connection_id = generate_ulid()
        
        # Handle connection
        handlers = WebSocketHandlers()
        await handlers.handle_connection(websocket, connection_id, ctx)
    except WebSocketDisconnect:
        # Client disconnected
        pass
    except Exception as e:
        # Error handling
        try:
            await websocket.close(code=1011, reason=f"Server error: {str(e)}")
        except:
            pass

