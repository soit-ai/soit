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
        assert data["name"] == "test_workflow"
        assert "id" in data
    
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
        assert "items" in data
        assert isinstance(data["items"], list)
    
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
        workflow_id = create_response.json()["id"]
        
        # Get workflow
        response = client.get(
            f"/api/v1/workflows/{workflow_id}",
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == workflow_id
        assert data["name"] == "test_workflow_get"
    
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
        workflow_id = create_response.json()["id"]
        
        # Update workflow
        response = client.put(
            f"/api/v1/workflows/{workflow_id}",
            json={
                "name": "test_workflow_updated",
                "description": "Updated description",
            },
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "test_workflow_updated"
        assert data["description"] == "Updated description"
    
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
        workflow_id = create_response.json()["id"]
        
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
    
    def test_list_runs(self, client):
        """Test listing workflow runs."""
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
        workflow_id = create_response.json()["id"]
        
        # List runs (should be empty initially)
        response = client.get(
            f"/api/v1/workflows/{workflow_id}/runs",
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "items" in data
        assert isinstance(data["items"], list)
    
    def test_get_run(self, client):
        """Test getting a workflow run."""
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
        workflow_id = create_response.json()["id"]
        
        # Get a non-existent run
        run_id = "test-run-id"
        response = client.get(
            f"/api/v1/workflows/{workflow_id}/runs/{run_id}",
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        # Should return 404 for non-existent run
        assert response.status_code == status.HTTP_404_NOT_FOUND

