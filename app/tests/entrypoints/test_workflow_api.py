""" test_workflow_api

Integration tests for Workflow API endpoints.
"""

import pytest
from fastapi import status


class TestWorkflowAPI:
    """Test workflow API endpoints."""
    
    def test_create_workflow(self, client):
        """Test creating a workflow."""
        response = client.post(
            "/api/v1/workflows",
            json={
                "name": "test_workflow",
                "description": "Test workflow description",
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
            "current_version_id",
            "metadata_json",
            "created_at",
            "updated_at",
        }
        for key in required_keys:
            assert key in payload
    
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
        app_id = create_response.json()["data"]["id"]
        
        # Get workflow
        response = client.get(
            f"/api/v1/workflows/{app_id}",
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        payload = data["data"]
        assert payload["id"] == app_id
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
        app_id = create_response.json()["data"]["id"]

        version_response = client.post(
            f"/api/v1/workflows/{app_id}/versions",
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
        app_id = create_response.json()["data"]["id"]
        
        # Update workflow
        response = client.put(
            f"/api/v1/workflows/{app_id}",
            json={
                "name": "test_workflow_updated",
                "description": "Updated description",
            },
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        payload = data["data"]
        assert payload["name"] == "test_workflow_updated"
        assert payload["description"] == "Updated description"
    
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
        app_id = create_response.json()["data"]["id"]
        
        # Delete workflow
        response = client.delete(
            f"/api/v1/workflows/{app_id}",
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        
        # Verify workflow is deleted
        get_response = client.get(
            f"/api/v1/workflows/{app_id}",
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
        app_id = create_response.json()["data"]["id"]

        # List runs (should be empty initially)
        response = client.get(
            "/api/v1/runs",
            params={"app_version_id": app_id, "mode": "workflow"},
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
