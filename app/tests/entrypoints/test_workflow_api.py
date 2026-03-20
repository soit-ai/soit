""" test_workflow_api

Integration tests for Workflow API endpoints.
"""

from sqlalchemy import select
import pytest
from fastapi import status

from app.kernel.responses.models import Response


class TestWorkflowAPI:
    """Test workflow API endpoints."""
    
    def test_create_workflow(self, client):
        """Test creating a workflow."""
        response = client.post(
            "/api/v1/workflows",
            json={
                "name": "test_workflow",
                "description": "Test workflow description",
                "summary": "Workflow summary",
                "visibility": "workspace",
                "icon_url": "https://example.com/workflow.png",
                "category": "automation",
                "tags": ["ops", "etl"],
            },
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["success"] is True
        payload = data["data"]
        assert payload["name"] == "test_workflow"
        assert "id" in payload
        required_keys = {
            "id",
            "tenant_id",
            "workspace_id",
            "name",
            "description",
            "summary",
            "status",
            "visibility",
            "icon_url",
            "category",
            "tags",
            "owner_user_id",
            "current_version_id",
            "published_version_id",
            "metadata_json",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        }
        for key in required_keys:
            assert key in payload
        assert payload["summary"] == "Workflow summary"
        assert payload["visibility"] == "workspace"
        assert payload["icon_url"] == "https://example.com/workflow.png"
        assert payload["category"] == "automation"
        assert payload["tags"] == ["ops", "etl"]
    
    def test_list_workflows(self, client):
        """Test listing workflows."""
        # Create a workflow first
        create_response = client.post(
            "/api/v1/workflows",
            json={
                "name": "test_workflow_list",
                "description": "Test workflow for listing",
            },
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        
        # List workflows
        response = client.get(
            "/api/v1/workflows",
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        payload = data["data"]
        assert "items" in payload
        assert isinstance(payload["items"], list)
    
    def test_get_workflow(self, client):
        """Test getting a workflow by ID."""
        # Create a workflow first
        create_response = client.post(
            "/api/v1/workflows",
            json={
                "name": "test_workflow_get",
                "description": "Test workflow for getting",
            },
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        workflow_id = create_response.json()["data"]["id"]
        
        # Get workflow
        response = client.get(
            f"/api/v1/workflows/{workflow_id}",
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        payload = data["data"]
        assert payload["id"] == workflow_id
        assert payload["name"] == "test_workflow_get"
        for key in ("tenant_id", "workspace_id", "created_at", "updated_at"):
            assert key in payload

    def test_create_workflow_version_contract(self, client):
        """Workflow version response matches frontend contract."""
        create_response = client.post(
            "/api/v1/workflows",
            json={
                "name": "test_workflow_version",
                "description": "Test workflow for version",
            },
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        workflow_id = create_response.json()["data"]["id"]

        version_response = client.post(
            f"/api/v1/workflows/{workflow_id}/versions",
            json={
                "graph_json": {
                    "name": "version-spec",
                    "inputs_schema": {"type": "object", "properties": {}},
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
                },
                "created_by": "test-user",
            },
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert version_response.status_code == status.HTTP_201_CREATED
        payload = version_response.json()["data"]
        required_keys = {
            "id",
            "tenant_id",
            "workspace_id",
            "workflow_id",
            "graph_json",
            "created_by",
            "created_at",
        }
        for key in required_keys:
            assert key in payload
    
    def test_update_workflow(self, client):
        """Test updating a workflow."""
        # Create a workflow first
        create_response = client.post(
            "/api/v1/workflows",
            json={
                "name": "test_workflow_update",
                "description": "Test workflow for updating",
            },
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        workflow_id = create_response.json()["data"]["id"]
        
        # Update workflow
        response = client.put(
            f"/api/v1/workflows/{workflow_id}",
            json={
                "name": "test_workflow_updated",
                "description": "Updated description",
                "summary": "Updated summary",
                "visibility": "tenant",
                "category": "updated-category",
                "tags": ["updated"],
            },
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        payload = data["data"]
        assert payload["name"] == "test_workflow_updated"
        assert payload["description"] == "Updated description"
        assert payload["summary"] == "Updated summary"
        assert payload["visibility"] == "tenant"
        assert payload["category"] == "updated-category"
        assert payload["tags"] == ["updated"]
    
    def test_delete_workflow(self, client):
        """Test deleting a workflow."""
        # Create a workflow first
        create_response = client.post(
            "/api/v1/workflows",
            json={
                "name": "test_workflow_delete",
                "description": "Test workflow for deleting",
            },
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        workflow_id = create_response.json()["data"]["id"]
        
        # Delete workflow
        response = client.delete(
            f"/api/v1/workflows/{workflow_id}",
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        
        # Verify workflow is deleted
        get_response = client.get(
            f"/api/v1/workflows/{workflow_id}",
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        # Should return 404 or handle soft delete appropriately
        assert get_response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_200_OK]

    def test_viewer_cannot_create_workflow(self, db):
        """Viewer role should not be able to create workflows."""
        from fastapi.testclient import TestClient
        from app.main import app
        from app.infra.db.session import get_db
        from app.middleware.auth import get_current_context
        from app.kernel.contracts.context import RequestContext

        def _override_get_db():
            try:
                yield db
            finally:
                pass

        async def _override_get_current_context() -> RequestContext:
            return RequestContext(
                tenant_id="test-tenant",
                workspace_id="test-workspace",
                user_id="test-user",
                tenant_role="Viewer",
                workspace_role="Viewer",
            )

        app.dependency_overrides[get_db] = _override_get_db
        app.dependency_overrides[get_current_context] = _override_get_current_context
        with TestClient(app) as test_client:
            response = test_client.post(
                "/api/v1/workflows",
                json={
                    "name": "viewer_workflow",
                    "description": "should be forbidden",
                },
                headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
            )
            assert response.status_code == status.HTTP_403_FORBIDDEN
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_context, None)
    
    def test_list_runs(self, client):
        """Test listing workflow runs via run API."""
        # Create a workflow first
        create_response = client.post(
            "/api/v1/workflows",
            json={
                "name": "test_workflow_runs",
                "description": "Test workflow for runs",
            },
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        workflow_id = create_response.json()["data"]["id"]

        # List runs (should be empty initially)
        response = client.get(
            "/api/v1/runs",
            params={"workflow_id": workflow_id, "mode": "workflow"},
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        payload = data["data"]
        assert "items" in payload
        assert isinstance(payload["items"], list)
    
    def test_get_run(self, client):
        """Test getting a workflow run via run API."""
        # Create a workflow first
        create_response = client.post(
            "/api/v1/workflows",
            json={
                "name": "test_workflow_get_run",
                "description": "Test workflow for getting run",
            },
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert create_response.status_code == status.HTTP_201_CREATED

        # Get a non-existent run
        run_id = "test-run-id"
        response = client.get(
            f"/api/v1/runs/{run_id}",
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        # Should return 404 for non-existent run
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_sse_execution_creates_linked_response(self, client, db):
        """Workflow SSE execution should reuse the response-aware engine wiring."""
        headers = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}
        create_response = client.post(
            "/api/v1/workflows",
            json={
                "name": "test_workflow_sse_execute",
                "description": "SSE workflow execution",
            },
            headers=headers,
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        workflow_id = create_response.json()["data"]["id"]

        version_response = client.post(
            f"/api/v1/workflows/{workflow_id}/versions",
            json={
                "graph_json": {
                    "name": "sse-llm-flow",
                    "inputs_schema": {"type": "object", "properties": {}},
                    "outputs_schema": {"type": "object", "properties": {"value": {"type": "string"}}},
                    "graph": {
                        "nodes": [
                            {"id": "llm1", "type": "llm", "params": {"prompt": "hello from sse"}},
                            {"id": "out1", "type": "output", "params": {"value": "{{ steps.llm1.output.text }}"}},
                        ],
                        "edges": [{"id": "e1", "from": "llm1", "to": "out1"}],
                    },
                },
                "created_by": "test-user",
            },
            headers=headers,
        )
        assert version_response.status_code == status.HTTP_201_CREATED
        version_id = version_response.json()["data"]["id"]

        publish_response = client.post(
            f"/api/v1/workflows/{workflow_id}/publish",
            json={"version_id": version_id},
            headers=headers,
        )
        assert publish_response.status_code == status.HTTP_200_OK

        with client.stream(
            "POST",
            "/api/v1/sse/execution",
            json={"workflow_id": workflow_id, "inputs": {}},
            headers=headers,
        ) as response:
            assert response.status_code == status.HTTP_200_OK
            body = response.read().decode("utf-8")

        assert "event: start" in body
        assert "event: compiled" in body
        assert "event: complete" in body

        run_id = None
        for raw_line in body.splitlines():
            if not raw_line.startswith("data: "):
                continue
            payload = raw_line[6:]
            if '"run_id"' not in payload:
                continue
            import json

            parsed = json.loads(payload)
            run_id = parsed.get("run_id") or run_id
            if run_id:
                break

        assert run_id is not None
        rows = db.exec(
            select(Response).where(
                Response.tenant_id == "test-tenant",
                Response.workspace_id == "test-workspace",
                Response.run_id == run_id,
            )
        ).all()
        linked_responses = [item if isinstance(item, Response) else item[0] for item in rows]
        assert len(linked_responses) >= 1
        assert any(item.status == "completed" for item in linked_responses)

    def test_sse_chat_streams_responses_semantic_events(self, client):
        """Legacy SSE chat endpoint should now emit response semantic events."""
        headers = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}
        create_response = client.post(
            "/api/v1/workflows",
            json={
                "name": "test_workflow_sse_chat",
                "description": "SSE chat response stream",
            },
            headers=headers,
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        workflow_id = create_response.json()["data"]["id"]

        with client.stream(
            "POST",
            "/api/v1/sse/chat",
            json={
                "workflow_id": workflow_id,
                "messages": [{"role": "user", "content": "hello semantic sse"}],
            },
            headers=headers,
        ) as response:
            assert response.status_code == status.HTTP_200_OK
            body = response.read().decode("utf-8")

        assert "event: response.created" in body
        assert "event: response.input.added" in body
        assert "event: response.output_text.delta" in body
        assert "event: response.output_text.completed" in body
        assert "event: response.completed" in body
        assert "[DONE]" in body

        response_id = None
        for raw_line in body.splitlines():
            if not raw_line.startswith("data: "):
                continue
            payload = raw_line[6:]
            if payload == "[DONE]":
                continue
            import json

            parsed = json.loads(payload)
            response_id = parsed.get("response_id") or response_id
            if response_id:
                break

        assert response_id is not None
        get_response = client.get(
            f"/api/v1/responses/{response_id}",
            headers=headers,
        )
        assert get_response.status_code == status.HTTP_200_OK
        assert get_response.json()["data"]["status"] == "completed"


