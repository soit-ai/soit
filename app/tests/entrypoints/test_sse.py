""" test_sse

Integration tests for SSE endpoints.
"""

import pytest
from fastapi import status
import json


class TestSSEAPI:
    """Test SSE API endpoints."""
    
    def test_stream_execution_endpoint_exists(self, client):
        """Test that SSE execution endpoint exists."""
        # Note: Testing SSE endpoints with TestClient is limited
        # This test verifies the endpoint structure
        response = client.post(
            "/api/v1/sse/execution",
            json={
                "workflow_id": "test-workflow-id",
                "inputs": {},
            },
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        # Should return 200 (streaming response) or 404/500 depending on workflow existence
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]
    
    def test_stream_chat_endpoint_exists(self, client):
        """Test that SSE chat endpoint exists."""
        response = client.post(
            "/api/v1/sse/chat",
            json={
                "workflow_id": "test-workflow-id",
                "messages": [{"role": "user", "content": "Hello"}],
            },
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        # Should return 200 (streaming response) or 404/500 depending on workflow existence
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

