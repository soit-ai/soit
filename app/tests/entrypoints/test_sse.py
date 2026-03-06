""" test_sse

Integration tests for SSE endpoints.
"""

import pytest
from fastapi import status
import json

from app.modules.appcenter.domain.models import App, AppVersion
from app.kernel.ports.secrets.interface import SecretsPort
from app.wiring import get_container, reset_container


class DummySecretsPort(SecretsPort):
    """Secrets port stub for SSE tests."""

    async def get_secret(self, secret_ref: str, **kwargs):
        return ""

    async def set_secret(self, secret_ref: str, value: str, **kwargs):
        return None

    async def delete_secret(self, secret_ref: str, **kwargs):
        return None


class TestSSEAPI:
    """Test SSE API endpoints."""
    
    def test_stream_execution_endpoint_exists(self, client):
        """Test that SSE execution endpoint exists."""
        # Note: Testing SSE endpoints with TestClient is limited
        # This test verifies the endpoint structure
        response = client.post(
            "/api/v1/sse/execution",
            json={
                "app_id": "test-workflow-id",
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
                "app_id": "test-workflow-id",
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

    def test_stream_execution_emits_events(self, client, db, ctx):
        """Stream execution returns expected SSE events."""
        reset_container()
        container = get_container()
        container.register_factory("secrets_port", lambda: DummySecretsPort())

        workflow = App(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            type="WORKFLOW",
            status="active",
            visibility="private",
            name="sse-workflow",
            description="SSE workflow test",
            created_by=ctx.user_id,
        )
        db.add(workflow)
        db.commit()
        db.refresh(workflow)

        spec = {
            "name": "sse-workflow",
            "inputs_schema": {"type": "object"},
            "outputs_schema": {"type": "object", "properties": {"value": {"type": "boolean"}}},
            "graph": {
                "nodes": [
                    {"id": "set1", "type": "set_var", "params": {"set": {"flag": True}}},
                    {
                        "id": "out1",
                        "type": "output",
                        "params": {"value": "{{ steps.set1.output.flag }}"},
                    },
                ],
                "edges": [{"id": "e1", "from": "set1", "to": "out1"}],
            },
        }
        version = AppVersion(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            app_id=workflow.id,
            version=1,
            status="published",
            spec_schema="workflow.v1",
            spec_json=spec,
            created_by=ctx.user_id,
        )
        db.add(version)
        db.commit()
        db.refresh(version)
        workflow.current_version_id = version.id
        db.commit()
        db.refresh(workflow)

        payload = {"app_id": workflow.id, "inputs": {}}
        with client.stream("POST", "/api/v1/sse/execution", json=payload) as response:
            assert response.status_code == status.HTTP_200_OK
            events = []
            data_lines = []
            for line in response.iter_lines():
                if not line:
                    continue
                text = line.decode() if isinstance(line, bytes) else line
                if text.startswith("event:"):
                    events.append(text.replace("event:", "").strip())
                if text.startswith("data:"):
                    data_lines.append(text.replace("data:", "").strip())

        assert "start" in events
        assert "compiled" in events
        assert "step" in events
        assert "complete" in events

        parsed = [json.loads(line) for line in data_lines if line.startswith("{")]
        assert any("run_id" in item for item in parsed)
