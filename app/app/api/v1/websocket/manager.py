""" manager

WebSocket connection manager.
"""

from typing import Dict, Set
from fastapi import WebSocket, WebSocketDisconnect
import json
import asyncio

from app.kernel.contracts.context import RequestContext


class ConnectionManager:
    """Manages WebSocket connections."""
    
    def __init__(self):
        """Initialize connection manager."""
        self.active_connections: Dict[str, WebSocket] = {}
        """Active WebSocket connections by connection ID."""
        
        self.user_connections: Dict[str, Set[str]] = {}
        """User ID to connection IDs mapping."""
        
        self.run_subscriptions: Dict[str, Set[str]] = {}
        """Run ID to connection IDs mapping."""
    
    async def connect(self, websocket: WebSocket, connection_id: str, ctx: RequestContext):
        """Accept WebSocket connection.
        
        Args:
            websocket: WebSocket instance.
            connection_id: Unique connection ID.
            ctx: Request context.
        """
        await websocket.accept()
        self.active_connections[connection_id] = websocket
        
        # Track user connections
        user_id = ctx.user_id
        if user_id not in self.user_connections:
            self.user_connections[user_id] = set()
        self.user_connections[user_id].add(connection_id)
    
    def disconnect(self, connection_id: str, ctx: RequestContext):
        """Disconnect WebSocket connection.
        
        Args:
            connection_id: Connection ID.
            ctx: Request context.
        """
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
        
        # Remove from user connections
        user_id = ctx.user_id
        if user_id in self.user_connections:
            self.user_connections[user_id].discard(connection_id)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]
        
        # Remove from run subscriptions
        for run_id, conn_ids in self.run_subscriptions.items():
            conn_ids.discard(connection_id)
            if not conn_ids:
                del self.run_subscriptions[run_id]
    
    async def send_personal_message(self, message: dict, connection_id: str):
        """Send message to a specific connection.
        
        Args:
            message: Message dictionary.
            connection_id: Connection ID.
        """
        if connection_id in self.active_connections:
            websocket = self.active_connections[connection_id]
            try:
                await websocket.send_json(message)
            except Exception:
                # Connection closed, remove it
                del self.active_connections[connection_id]
    
    async def broadcast_to_run(self, run_id: str, message: dict):
        """Broadcast message to all connections subscribed to a run.
        
        Args:
            run_id: Run ID.
            message: Message dictionary.
        """
        if run_id in self.run_subscriptions:
            connection_ids = list(self.run_subscriptions[run_id])
            for connection_id in connection_ids:
                await self.send_personal_message(message, connection_id)
    
    def subscribe_to_run(self, connection_id: str, run_id: str):
        """Subscribe connection to run updates.
        
        Args:
            connection_id: Connection ID.
            run_id: Run ID.
        """
        if run_id not in self.run_subscriptions:
            self.run_subscriptions[run_id] = set()
        self.run_subscriptions[run_id].add(connection_id)
    
    def unsubscribe_from_run(self, connection_id: str, run_id: str):
        """Unsubscribe connection from run updates.
        
        Args:
            connection_id: Connection ID.
            run_id: Run ID.
        """
        if run_id in self.run_subscriptions:
            self.run_subscriptions[run_id].discard(connection_id)
            if not self.run_subscriptions[run_id]:
                del self.run_subscriptions[run_id]


# Global connection manager instance
manager = ConnectionManager()

