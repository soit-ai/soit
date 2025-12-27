""" test_chat_api

Integration tests for Chat API endpoints.
"""

import pytest
from fastapi import status


class TestChatAPI:
    """Test chat API endpoints."""
    
    def test_get_history_no_conversation(self, client):
        """Test getting chat history without conversation ID."""
        response = client.get(
            "/api/v1/chat/history",
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "items" in data
        assert isinstance(data["items"], list)
    
    def test_get_history_with_conversation(self, client):
        """Test getting chat history with conversation ID."""
        # This test requires a conversation to exist
        # For now, just test the endpoint structure
        conversation_id = "test-conversation-id"
        response = client.get(
            f"/api/v1/chat/history?conversation_id={conversation_id}",
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        # Should return 200 or 404 depending on whether conversation exists
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
    
    def test_delete_conversation(self, client):
        """Test deleting a conversation."""
        # Create a conversation first (if API supports it)
        # For now, just test the endpoint structure
        conversation_id = "test-conversation-id"
        response = client.delete(
            f"/api/v1/chat/history/{conversation_id}",
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        # Should return 204 or 404 depending on whether conversation exists
        assert response.status_code in [status.HTTP_204_NO_CONTENT, status.HTTP_404_NOT_FOUND]

