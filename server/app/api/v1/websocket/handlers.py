""" handlers

WebSocket request handlers.
"""

import logging
import json

from app.kernel.contracts.context import RequestContext
from app.api.v1.websocket.manager import manager


class WebSocketHandlers:
    """Handlers for WebSocket endpoints."""
    
    def __init__(self):
        """Initialize handlers."""
        self.logger = logging.getLogger(__name__)
    
    async def handle_connection(
        self,
        websocket,
        connection_id: str,
        ctx: RequestContext,
    ):
        """Handle WebSocket connection.
        
        Args:
            websocket: WebSocket instance.
            connection_id: Connection ID.
            ctx: Request context.
        """
        await manager.connect(websocket, connection_id, ctx)
        
        try:
            # Send welcome message
            await manager.send_personal_message(
                {
                    "type": "connected",
                    "connection_id": connection_id,
                },
                connection_id,
            )
            
            # Handle incoming messages
            while True:
                data = await websocket.receive_text()
                try:
                    message = json.loads(data)
                    await self.handle_message(websocket, connection_id, ctx, message)
                except json.JSONDecodeError:
                    await manager.send_personal_message(
                        {
                            "type": "error",
                            "message": "Invalid JSON",
                        },
                        connection_id,
                    )
        except Exception as exc:
            self.logger.info(
                "websocket.connection.closed",
                extra={
                    "connection_id": connection_id,
                    "user_id": ctx.user_id,
                    "error": str(exc),
                },
            )
        finally:
            manager.disconnect(connection_id, ctx)
    
    async def handle_message(
        self,
        websocket,
        connection_id: str,
        ctx: RequestContext,
        message: dict,
    ):
        """Handle incoming WebSocket message.
        
        Args:
            websocket: WebSocket instance.
            connection_id: Connection ID.
            ctx: Request context.
            message: Message dictionary.
        """
        msg_type = message.get("type")
        
        if msg_type == "subscribe":
            # Subscribe to run updates
            run_id = message.get("run_id")
            if run_id:
                manager.subscribe_to_run(connection_id, run_id)
                await manager.send_personal_message(
                    {
                        "type": "subscribed",
                        "run_id": run_id,
                    },
                    connection_id,
                )
        elif msg_type == "unsubscribe":
            # Unsubscribe from run updates
            run_id = message.get("run_id")
            if run_id:
                manager.unsubscribe_from_run(connection_id, run_id)
                await manager.send_personal_message(
                    {
                        "type": "unsubscribed",
                        "run_id": run_id,
                    },
                    connection_id,
                )
        elif msg_type == "ping":
            # Heartbeat
            await manager.send_personal_message(
                {
                    "type": "pong",
                },
                connection_id,
            )
        else:
            await manager.send_personal_message(
                {
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}",
                },
                connection_id,
            )
