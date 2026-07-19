""" test_workflow_api

Integration tests for Workflow API endpoints.
"""

import pytest
from fastapi import status
from sqlalchemy import select

from app.kernel.runtime.db.models.responses import Response
from app.kernel.runtime.db.models.runs import Run
from app.modules.workflow.domain.models import WorkflowPublish
from tests.fixtures.workflow_specs import canonical_workflow_spec


class TestWorkflowAPI:
    """Test workflow API endpoints."""

    def test_get_workflow_capabilities(self, client):
        headers = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}

        response = client.get("/api/v1/workflows/capabilities", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        payload = response.json()["data"]
        assert payload["builder_node_types"] == [
            "input",
            "transform",
            "set_var",
            "llm",
            "retrieve",
            "tool",
            "condition",
            "output",
        ]
        assert payload["compatibility_node_types"] == ["http", "node"]
        assert payload["capabilities"] == [
            {"type": "input", "ui_type": "input-node", "category": "input", "executable": True},
            {"type": "transform", "ui_type": "transform-node", "category": "data", "executable": True},
            {
                "type": "set_var",
                "ui_type": "variable-assignment-node",
                "category": "data",
                "executable": True,
            },
            {"type": "llm", "ui_type": "llm-node", "category": "model", "executable": True},
            {
                "type": "retrieve",
                "ui_type": "knowledge-search-node",
                "category": "data",
                "executable": True,
            },
            {"type": "tool", "ui_type": "tool-node", "category": "tool", "executable": True},
            {
                "type": "condition",
                "ui_type": "conditional-node",
                "category": "flow",
                "executable": True,
            },
            {"type": "output", "ui_type": "output-node", "category": "output", "executable": True},
        ]

    def test_create_workflow_version_rejects_spoofed_created_by(self, client):
        headers = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}
        create_response = client.post(
            "/api/v1/workflows",
            json={"name": "reject-version-actor-spoof"},
            headers=headers,
        )
        assert create_response.status_code == status.HTTP_201_CREATED

        response = client.post(
            f"/api/v1/workflows/{create_response.json()['data']['id']}/versions",
            json={"graph_json": canonical_workflow_spec(), "created_by": "spoofed-user"},
            headers=headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_import_workflow_dsl_rejects_spoofed_created_by(self, client):
        headers = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}
        create_response = client.post(
            "/api/v1/workflows",
            json={"name": "reject-import-actor-spoof"},
            headers=headers,
        )
        assert create_response.status_code == status.HTTP_201_CREATED

        response = client.post(
            f"/api/v1/workflows/{create_response.json()['data']['id']}/dsl",
            json={
                "dsl": canonical_workflow_spec(),
                "format": "json",
                "created_by": "spoofed-user",
            },
            headers=headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_create_workflow_version_empty_body_preserves_validation_response(self, client):
        headers = {
            "Content-Type": "application/json",
            "X-Tenant-Id": "test-tenant",
            "X-Workspace-Id": "test-workspace",
        }

        response = client.post(
            "/api/v1/workflows/wf-empty-version-body/versions",
            content=b"",
            headers=headers,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_import_workflow_dsl_empty_body_preserves_validation_response(self, client):
        headers = {
            "Content-Type": "application/json",
            "X-Tenant-Id": "test-tenant",
            "X-Workspace-Id": "test-workspace",
        }

        response = client.post(
            "/api/v1/workflows/wf-empty-import-body/dsl",
            content=b"",
            headers=headers,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.parametrize(
        "path",
        [
            "/api/v1/workflows/wf-invalid-bytes/versions",
            "/api/v1/workflows/wf-invalid-bytes/dsl",
        ],
    )
    def test_workflow_actor_guard_invalid_text_bytes_preserve_validation_response(self, client, path):
        headers = {
            "Content-Type": "text/plain",
            "X-Tenant-Id": "test-tenant",
            "X-Workspace-Id": "test-workspace",
        }

        response = client.post(path, content=b"\xff", headers=headers)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.parametrize(
        "path",
        [
            "/api/v1/workflows/wf-malformed-json/versions",
            "/api/v1/workflows/wf-malformed-json/dsl",
        ],
    )
    def test_workflow_actor_guard_malformed_json_preserves_validation_response(self, client, path):
        headers = {
            "Content-Type": "application/json",
            "X-Tenant-Id": "test-tenant",
            "X-Workspace-Id": "test-workspace",
        }

        response = client.post(path, content=b"{", headers=headers)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.parametrize(
        ("path", "payload"),
        [
            ("/api/v1/workflows/wf-array-body/versions", []),
            ("/api/v1/workflows/wf-scalar-body/versions", "created_by"),
            ("/api/v1/workflows/wf-array-body/dsl", []),
            ("/api/v1/workflows/wf-scalar-body/dsl", "created_by"),
        ],
    )
    def test_workflow_actor_guard_non_object_json_preserves_validation_response(self, client, path, payload):
        headers = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}

        response = client.post(path, json=payload, headers=headers)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.parametrize(
        "path",
        [
            "/api/v1/workflows/wf-wrong-media/versions",
            "/api/v1/workflows/wf-wrong-media/dsl",
        ],
    )
    def test_workflow_actor_guard_ignores_wrong_media_type(self, client, path):
        headers = {
            "Content-Type": "text/plain; charset=utf-8",
            "X-Tenant-Id": "test-tenant",
            "X-Workspace-Id": "test-workspace",
        }

        response = client.post(
            path,
            content=b'{"created_by":"spoofed-user"}',
            headers=headers,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.parametrize(
        "path",
        [
            "/api/v1/workflows/wf-structured-json/versions",
            "/api/v1/workflows/wf-structured-json/dsl",
        ],
    )
    def test_workflow_actor_guard_inspects_structured_json_media_type(self, client, path):
        headers = {
            "Content-Type": "Application/Vnd.Soit+Json; charset=utf-8",
            "X-Tenant-Id": "test-tenant",
            "X-Workspace-Id": "test-workspace",
        }

        response = client.post(
            path,
            content=b'{"created_by":"spoofed-user"}',
            headers=headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.parametrize(
        ("path", "payload"),
        [
            (
                "/api/v1/workflows/wf-viewer-actor/versions",
                {"graph_json": canonical_workflow_spec(), "created_by": "spoofed-user"},
            ),
            (
                "/api/v1/workflows/wf-viewer-actor/dsl",
                {
                    "dsl": canonical_workflow_spec(),
                    "format": "json",
                    "created_by": "spoofed-user",
                },
            ),
        ],
    )
    def test_workflow_actor_guard_authorization_precedes_actor_rejection(self, client, path, payload):
        from app.kernel.contracts.context import RequestContext
        from app.main import app
        from app.middleware.auth import get_current_context

        async def _override_get_current_context() -> RequestContext:
            return RequestContext(
                tenant_id="test-tenant",
                workspace_id="test-workspace",
                user_id="test-viewer",
                tenant_role="Viewer",
                workspace_role="Viewer",
            )

        previous_override = app.dependency_overrides.get(get_current_context)
        app.dependency_overrides[get_current_context] = _override_get_current_context
        try:
            response = client.post(
                path,
                json=payload,
                headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
            )
        finally:
            if previous_override is None:
                app.dependency_overrides.pop(get_current_context, None)
            else:
                app.dependency_overrides[get_current_context] = previous_override

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_workflow_version_uses_authenticated_actor(self, client):
        headers = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}
        create_response = client.post(
            "/api/v1/workflows",
            json={"name": "authenticated-version-actor"},
            headers=headers,
        )
        assert create_response.status_code == status.HTTP_201_CREATED

        response = client.post(
            f"/api/v1/workflows/{create_response.json()['data']['id']}/versions",
            json={"graph_json": canonical_workflow_spec()},
            headers=headers,
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["data"]["created_by"] == "test-user"

    def test_import_workflow_dsl_uses_authenticated_actor(self, client):
        headers = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}
        create_response = client.post(
            "/api/v1/workflows",
            json={"name": "authenticated-import-actor"},
            headers=headers,
        )
        assert create_response.status_code == status.HTTP_201_CREATED

        response = client.post(
            f"/api/v1/workflows/{create_response.json()['data']['id']}/dsl",
            json={"dsl": canonical_workflow_spec(), "format": "json"},
            headers=headers,
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["data"]["created_by"] == "test-user"

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

    def test_create_ticket_triage_template_workflow(self, client):
        headers = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}
        response = client.post(
            "/api/v1/workflows/templates/ticket-triage",
            json={"name": "ticket-triage-template-api"},
            headers=headers,
        )

        assert response.status_code == status.HTTP_201_CREATED
        payload = response.json()["data"]
        assert payload["name"] == "ticket-triage-template-api"
        assert payload["published_version_id"] is None
        assert payload["metadata_json"]["template_key"] == "ticket_triage"

        version_response = client.get(
            f"/api/v1/workflows/{payload['id']}/version/current",
            headers=headers,
        )
        assert version_response.status_code == status.HTTP_200_OK
        graph = version_response.json()["data"]["graph_json"]["graph"]
        assert [node["id"] for node in graph["nodes"]] == [
            "start",
            "knowledge_search",
            "classify",
            "approval",
            "ticket_tool",
            "response",
            "end",
        ]

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

    def test_workflow_workbench_returns_rows_and_runtime_metrics(self, client, db):
        """Workflow workbench should aggregate workflow state and run health."""
        from app.kernel.commons.time import utc_now

        headers = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}
        published_response = client.post(
            "/api/v1/workflows",
            json={"name": "Published Workflow", "description": "Ready workflow"},
            headers=headers,
        )
        assert published_response.status_code == status.HTTP_201_CREATED
        published_payload = published_response.json()["data"]
        workflow_id = published_payload["id"]
        version_id = published_payload["current_version_id"]

        publish_response = client.post(
            f"/api/v1/workflows/{workflow_id}/publish",
            json={"version_id": version_id},
            headers=headers,
        )
        assert publish_response.status_code == status.HTTP_200_OK

        draft_response = client.post(
            "/api/v1/workflows",
            json={"name": "Draft Workflow", "description": "Needs publish"},
            headers=headers,
        )
        assert draft_response.status_code == status.HTTP_201_CREATED

        now = utc_now()
        db.add_all(
            [
                Run(
                    id="run_workflow_workbench_success",
                    tenant_id="test-tenant",
                    workspace_id="test-workspace",
                    mode="workflow",
                    kind="workflow",
                    subject_kind="workflow",
                    subject_id=workflow_id,
                    subject_version_id=version_id,
                    status="succeeded",
                    input_summary="{}",
                    output_summary="done",
                    started_at=now,
                    ended_at=now,
                    duration_ms=1000,
                ),
                Run(
                    id="run_workflow_workbench_failed",
                    tenant_id="test-tenant",
                    workspace_id="test-workspace",
                    mode="workflow",
                    kind="workflow",
                    subject_kind="workflow",
                    subject_id=workflow_id,
                    subject_version_id=version_id,
                    status="failed",
                    input_summary="{}",
                    error_message="node failed",
                    started_at=now,
                    ended_at=now,
                    duration_ms=3000,
                ),
            ]
        )
        db.commit()

        response = client.get("/api/v1/workflows/workbench?page_size=20", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        payload = response.json()["data"]
        assert payload["summary"]["total_workflows"] == 2
        assert payload["summary"]["published_workflows"] == 1
        assert payload["summary"]["running_workflows"] == 1
        assert payload["summary"]["today_runs"] == 2
        assert payload["summary"]["avg_latency_ms"] == 2000
        assert payload["summary"]["success_rate"] == 50.0
        assert payload["summary"]["recent_exceptions"] == 1
        assert payload["tabs"]["all"] == 2
        assert payload["tabs"]["draft"] == 1
        assert payload["tabs"]["abnormal"] == 1

        published_row = next(item for item in payload["items"] if item["id"] == workflow_id)
        assert published_row["status"] == "abnormal"
        assert published_row["today_runs"] == 2
        assert published_row["avg_latency_ms"] == 2000
        assert published_row["success_rate"] == 50.0
        assert published_row["recent_exception_count"] == 1
        assert published_row["action_enabled"] is True
        assert published_row["last_run_at"] is not None

        draft_row = next(item for item in payload["items"] if item["name"] == "Draft Workflow")
        assert draft_row["status"] == "draft"
        assert draft_row["action_enabled"] is False

        items_response = client.get(
            "/api/v1/workflows/workbench/items?tab=abnormal&keyword=Published&page_size=1",
            headers=headers,
        )
        assert items_response.status_code == status.HTTP_200_OK
        items_payload = items_response.json()["data"]
        assert "summary" not in items_payload
        assert items_payload["page_size"] == 1
        assert items_payload["next_page_token"] is None
        assert [item["id"] for item in items_payload["items"]] == [workflow_id]

        paged_response = client.get("/api/v1/workflows/workbench/items?page_size=1", headers=headers)
        assert paged_response.status_code == status.HTTP_200_OK
        assert paged_response.json()["data"]["next_page_token"] is not None

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

        detail_response = client.get(
            f"/api/v1/workflows/{workflow_id}",
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert detail_response.status_code == status.HTTP_200_OK
        detail_payload = detail_response.json()["data"]
        assert detail_payload["current_version_id"] == payload["id"]
        assert detail_payload["published_version_id"] is None

    def test_create_workflow_version_preserves_original_spec_json(self, client):
        headers = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}
        create_response = client.post(
            "/api/v1/workflows",
            json={"name": "preserve-workflow-spec"},
            headers=headers,
        )
        assert create_response.status_code == status.HTTP_201_CREATED

        original_spec = canonical_workflow_spec()
        version_response = client.post(
            f"/api/v1/workflows/{create_response.json()['data']['id']}/versions",
            json={"graph_json": original_spec},
            headers=headers,
        )

        assert version_response.status_code == status.HTTP_201_CREATED
        assert version_response.json()["data"]["graph_json"] == original_spec

    def test_publish_workflow_promotes_existing_draft(self, client, db):
        headers = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}
        create_response = client.post(
            "/api/v1/workflows",
            json={
                "name": "test_workflow_publish",
                "description": "Test workflow for publish",
            },
            headers=headers,
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        workflow_payload = create_response.json()["data"]
        workflow_id = workflow_payload["id"]
        initial_version_id = workflow_payload["current_version_id"]

        version_response = client.post(
            f"/api/v1/workflows/{workflow_id}/versions",
            json={
                "graph_json": {
                    "name": "publish-spec",
                    "inputs_schema": {"type": "object", "properties": {}},
                    "outputs_schema": {"type": "object", "properties": {"value": {"type": "boolean"}}},
                    "graph": {
                        "nodes": [
                            {"id": "set1", "type": "set_var", "params": {"set": {"flag": True}}},
                            {"id": "out1", "type": "output", "params": {"value": "{{ steps.set1.output.flag }}"}},
                        ],
                        "edges": [{"id": "e1", "from": "set1", "to": "out1"}],
                    },
                },
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
        payload = publish_response.json()["data"]
        assert payload["current_version_id"] == version_id
        assert payload["published_version_id"] == version_id

        rollback_response = client.post(
            f"/api/v1/workflows/{workflow_id}/rollback",
            json={"version_id": initial_version_id, "notes": "rollback default"},
            headers=headers,
        )
        assert rollback_response.status_code == status.HTTP_200_OK
        rolled_back = rollback_response.json()["data"]
        assert rolled_back["current_version_id"] == version_id
        assert rolled_back["published_version_id"] == initial_version_id

        releases_response = client.get(
            f"/api/v1/workflows/{workflow_id}/releases",
            headers=headers,
        )
        assert releases_response.status_code == status.HTTP_200_OK
        releases = releases_response.json()["data"]["items"]
        assert len(releases) == 2
        assert releases[0]["action"] == "rollback"
        assert releases[0]["from_version_id"] == version_id
        assert releases[0]["to_version_id"] == initial_version_id
        assert releases[0]["notes"] == "rollback default"
        assert releases[1]["action"] == "publish"
        assert releases[1]["to_version_id"] == version_id

        rows = db.execute(
            select(WorkflowPublish)
            .where(WorkflowPublish.workflow_id == workflow_id)
            .order_by(WorkflowPublish.created_at.desc())
        ).scalars().all()
        assert len(rows) >= 2
        latest = rows[0]
        previous = rows[1]
        assert latest.action == "rollback"
        assert latest.from_version_id == version_id
        assert latest.to_version_id == initial_version_id
        assert latest.rollback_of_publish_id == previous.id
        assert latest.notes == "rollback default"

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

        from app.infra.db.session import get_db
        from app.kernel.contracts.context import RequestContext
        from app.main import app
        from app.middleware.auth import get_current_context

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
            params={"subject_kind": "workflow", "subject_id": workflow_id, "mode": "workflow"},
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
            f"/api/v1/workflows/{workflow_id}/stream",
            json={"inputs": {}},
            headers=headers,
        ) as response:
            assert response.status_code == status.HTTP_200_OK
            body = response.read().decode("utf-8")

        assert "event: start" in body
        assert "event: compiled" in body
        assert "event: complete" in body
        assert "workflow_id" not in body

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
        assert any(item.status == "succeeded" for item in linked_responses)

        with client.stream(
            "GET",
            f"/api/v1/runs/{run_id}/stream",
            headers=headers,
        ) as response:
            assert response.status_code == status.HTTP_200_OK
            replay_body = response.read().decode("utf-8")

        assert "event: run" in replay_body
        assert "event: complete" in replay_body

    def test_execute_ticket_tool_workflow_projects_tool_call_timeline(self, client):
        """Ticket demo workflow execution should expose tool-call detail through Responses timeline."""
        headers = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}
        create_response = client.post(
            "/api/v1/workflows",
            json={
                "name": "test_ticket_tool_workflow",
                "description": "Ticket workflow tool call demo",
            },
            headers=headers,
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        workflow_id = create_response.json()["data"]["id"]

        version_response = client.post(
            f"/api/v1/workflows/{workflow_id}/versions",
            json={
                "graph_json": {
                    "name": "ticket-tool-flow",
                    "inputs_schema": {"type": "object", "properties": {"ticket_id": {"type": "string"}}},
                    "outputs_schema": {"type": "object", "properties": {"value": {"type": "object"}}},
                    "graph": {
                        "nodes": [
                            {
                                "id": "ticket_tool",
                                "type": "tool",
                                "params": {
                                    "tool_ref": "tool:function:time_now",
                                    "ticket_id": "{{ inputs.ticket_id }}",
                                },
                            },
                            {
                                "id": "out1",
                                "type": "output",
                                "params": {
                                    "value": {
                                        "ticket_id": "{{ inputs.ticket_id }}",
                                        "tool_ref": "{{ steps.ticket_tool.output.result.tool_ref }}",
                                    }
                                },
                            },
                        ],
                        "edges": [{"id": "e1", "from": "ticket_tool", "to": "out1"}],
                    },
                },
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

        execute_response = client.post(
            f"/api/v1/workflows/{workflow_id}/execute",
            json={"ticket_id": "TCK-1001"},
            headers=headers,
        )
        assert execute_response.status_code == status.HTTP_200_OK
        run_id = execute_response.json()["data"]["run_id"]

        timeline_response = client.get(
            f"/api/v1/responses/by-run/{run_id}",
            headers=headers,
        )
        assert timeline_response.status_code == status.HTTP_200_OK
        items = timeline_response.json()["data"]["items"]
        tool_items = [item for item in items if item["tool_calls"]]
        assert len(tool_items) == 1
        tool_call = tool_items[0]["tool_calls"][0]
        assert tool_call["tool_name"] == "tool:function:time_now"
        assert tool_call["status"] == "completed"
        assert tool_call["arguments_json"]["ticket_id"] == "TCK-1001"

    def test_ticket_workflow_run_control_contract(self, client, db):
        """Ticket workflow run controls should pause/resume active runs and replay/retry failed runs."""
        headers = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}
        create_response = client.post(
            "/api/v1/workflows",
            json={
                "name": "test_ticket_workflow_controls",
                "description": "Ticket workflow run control demo",
            },
            headers=headers,
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        workflow_id = create_response.json()["data"]["id"]

        version_response = client.post(
            f"/api/v1/workflows/{workflow_id}/versions",
            json={
                "graph_json": {
                    "name": "ticket-control-flow",
                    "inputs_schema": {"type": "object", "properties": {"ticket_id": {"type": "string"}}},
                    "outputs_schema": {"type": "object", "properties": {"ticket_id": {"type": "string"}}},
                    "graph": {
                        "nodes": [
                            {
                                "id": "set_ticket",
                                "type": "set_var",
                                "params": {
                                    "key": "ticket_id",
                                    "value": "{{ inputs.ticket_id }}",
                                },
                            },
                            {
                                "id": "out1",
                                "type": "output",
                                "params": {"ticket_id": "{{ steps.set_ticket.output.value }}"},
                            }
                        ],
                        "edges": [{"id": "e1", "from": "set_ticket", "to": "out1"}],
                    },
                },
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

        running_run = Run(
            id="run_workflow_control_running",
            tenant_id="test-tenant",
            workspace_id="test-workspace",
            user_id="test-user",
            mode="workflow",
            kind="workflow",
            subject_kind="workflow",
            subject_id=workflow_id,
            subject_version_id=version_id,
            status="running",
            input_summary='{"ticket_id":"TCK-2001"}',
        )
        failed_run = Run(
            id="run_workflow_control_failed",
            tenant_id="test-tenant",
            workspace_id="test-workspace",
            user_id="test-user",
            mode="workflow",
            kind="workflow",
            subject_kind="workflow",
            subject_id=workflow_id,
            subject_version_id=version_id,
            status="failed",
            input_summary='{"ticket_id":"TCK-2002"}',
            error_code="ticket_failed",
            error_message="ticket workflow failed",
        )
        queued_run = Run(
            id="run_workflow_control_queued",
            tenant_id="test-tenant",
            workspace_id="test-workspace",
            user_id="test-user",
            mode="workflow",
            kind="workflow",
            subject_kind="workflow",
            subject_id=workflow_id,
            subject_version_id=version_id,
            status="queued",
            input_summary='{"ticket_id":"TCK-2004"}',
        )
        db.add(running_run)
        db.add(failed_run)
        db.add(queued_run)
        db.commit()

        pause_response = client.post(f"/api/v1/workflows/{workflow_id}/runs/{running_run.id}/pause", headers=headers)
        assert pause_response.status_code == status.HTTP_200_OK
        assert pause_response.json()["data"] == {"run_id": running_run.id, "status": "paused"}

        resume_response = client.post(f"/api/v1/workflows/{workflow_id}/runs/{running_run.id}/resume", headers=headers)
        assert resume_response.status_code == status.HTTP_200_OK
        assert resume_response.json()["data"] == {"run_id": running_run.id, "status": "running"}

        cancel_response = client.post(
            f"/api/v1/workflows/{workflow_id}/runs/{running_run.id}/cancel",
            json={"reason": "No longer needed"},
            headers=headers,
        )
        assert cancel_response.status_code == status.HTTP_200_OK
        assert cancel_response.json()["data"] == {"run_id": running_run.id, "status": "canceled"}
        db.refresh(running_run)
        assert running_run.status == "canceled"
        assert running_run.error_code == "workflow_run_canceled"
        assert running_run.error_message == "No longer needed"
        assert running_run.ended_at is not None

        fail_response = client.post(
            f"/api/v1/workflows/{workflow_id}/runs/{queued_run.id}/fail",
            json={"error_code": "manual_fail", "error_message": "Manual test failure"},
            headers=headers,
        )
        assert fail_response.status_code == status.HTTP_200_OK
        assert fail_response.json()["data"] == {"run_id": queued_run.id, "status": "failed"}
        db.refresh(queued_run)
        assert queued_run.status == "failed"
        assert queued_run.error_code == "manual_fail"
        assert queued_run.error_message == "Manual test failure"
        assert queued_run.ended_at is not None

        retry_response = client.post(f"/api/v1/workflows/{workflow_id}/runs/{failed_run.id}/retry", headers=headers)
        assert retry_response.status_code == status.HTTP_200_OK
        retry_payload = retry_response.json()["data"]
        assert retry_payload["run_id"]
        assert retry_payload["source_run_id"] == failed_run.id
        assert retry_payload["control_action"] == "retry"
        assert retry_payload["output"]["ticket_id"] == "TCK-2002"

        retry_canceled_response = client.post(f"/api/v1/workflows/{workflow_id}/runs/{running_run.id}/retry", headers=headers)
        assert retry_canceled_response.status_code == status.HTTP_200_OK
        retry_canceled_payload = retry_canceled_response.json()["data"]
        assert retry_canceled_payload["run_id"]
        assert retry_canceled_payload["source_run_id"] == running_run.id
        assert retry_canceled_payload["control_action"] == "retry"
        assert retry_canceled_payload["output"]["ticket_id"] == "TCK-2001"

        replay_response = client.post(
            f"/api/v1/workflows/{workflow_id}/runs/{failed_run.id}/replay",
            json={"ticket_id": "TCK-2003"},
            headers=headers,
        )
        assert replay_response.status_code == status.HTTP_200_OK
        replay_payload = replay_response.json()["data"]
        assert replay_payload["run_id"]
        assert replay_payload["source_run_id"] == failed_run.id
        assert replay_payload["control_action"] == "replay"
        assert replay_payload["output"]["ticket_id"] == "TCK-2003"


