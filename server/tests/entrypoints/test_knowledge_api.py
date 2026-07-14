"""Entrypoint tests for the knowledge API contract."""

from fastapi import status

from app.kernel.commons.time import utc_now
from app.kernel.runtime.db.models.runs import Run
from app.modules.knowledge.domain.models import (
    Knowledge,
    KnowledgeDocument,
    KnowledgeIndex,
    KnowledgeIngestTask,
)


def _headers() -> dict:
    return {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}


def test_knowledge_workbench_returns_rows_and_runtime_metrics(client, db):
    now = utc_now()
    ready_knowledge = Knowledge(
        id="knw_workbench_ready",
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        name="Support Knowledge",
        type="document",
        description="Runtime backed support knowledge",
        status="active",
        visibility="workspace",
        default_index_id="idx_workbench_ready",
        doc_count=2,
        chunk_count=8,
        last_ingested_at=now,
        last_indexed_at=now,
        created_by="user-1",
        updated_by="user-1",
        created_at=now,
        updated_at=now,
    )
    unconfigured_knowledge = Knowledge(
        id="knw_workbench_empty",
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        name="Empty Knowledge",
        type="qa",
        description="No content yet",
        status="active",
        visibility="workspace",
        doc_count=0,
        chunk_count=0,
        created_at=now,
        updated_at=now,
    )
    db.add_all(
        [
            ready_knowledge,
            unconfigured_knowledge,
            KnowledgeDocument(
                id="doc_workbench_ready",
                tenant_id="test-tenant",
                workspace_id="test-workspace",
                knowledge_id=ready_knowledge.id,
                doc_key="support-policy",
                version=1,
                is_latest=True,
                source_kind="upload",
                title="Support Policy",
                status="indexed",
                created_at=now,
                updated_at=now,
            ),
            KnowledgeIndex(
                id="idx_workbench_ready",
                tenant_id="test-tenant",
                workspace_id="test-workspace",
                knowledge_id=ready_knowledge.id,
                name="Primary Index",
                is_primary=True,
                provider="pgvector",
                embedding_model_ref="model:test:embedding",
                dimension=1536,
                metric_type="cosine",
                status="ready",
                doc_count=2,
                chunk_count=8,
                vector_count=8,
                created_at=now,
                updated_at=now,
            ),
            KnowledgeIngestTask(
                id="ingest_workbench_done",
                tenant_id="test-tenant",
                workspace_id="test-workspace",
                knowledge_id=ready_knowledge.id,
                document_id="doc_workbench_ready",
                status="succeeded",
                payload_json={},
                created_at=now,
                updated_at=now,
            ),
            Run(
                id="run_knowledge_workbench_success",
                tenant_id="test-tenant",
                workspace_id="test-workspace",
                mode="knowledge_query",
                kind="knowledge",
                subject_kind="knowledge",
                subject_id=ready_knowledge.id,
                status="succeeded",
                input_summary="query",
                output_summary="hits",
                started_at=now,
                ended_at=now,
                duration_ms=1200,
            ),
            Run(
                id="run_knowledge_workbench_failed",
                tenant_id="test-tenant",
                workspace_id="test-workspace",
                mode="knowledge_query",
                kind="knowledge",
                subject_kind="knowledge",
                subject_id=ready_knowledge.id,
                status="failed",
                input_summary="query",
                error_message="retrieval failed",
                started_at=now,
                ended_at=now,
                duration_ms=2800,
            ),
        ]
    )
    db.commit()

    response = client.get("/api/v1/knowledge/workbench?page_size=20", headers=_headers())

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()["data"]
    assert payload["summary"]["total_knowledge_bases"] == 2
    assert payload["summary"]["ready_knowledge_bases"] == 0
    assert payload["summary"]["total_documents"] == 2
    assert payload["summary"]["total_chunks"] == 8
    assert payload["summary"]["today_calls"] == 2
    assert payload["summary"]["avg_latency_ms"] == 2000
    assert payload["summary"]["hit_rate"] == 50.0
    assert payload["summary"]["recent_exceptions"] == 1
    assert payload["tabs"]["all"] == 2
    assert payload["tabs"]["low_hit"] == 1
    assert payload["tabs"]["slow"] == 1
    assert payload["tabs"]["unconfigured"] == 1

    ready_row = next(item for item in payload["items"] if item["id"] == ready_knowledge.id)
    assert ready_row["status"] == "error"
    assert ready_row["content_source"] == "Upload"
    assert ready_row["document_count"] == 2
    assert ready_row["chunk_count"] == 8
    assert ready_row["today_calls"] == 2
    assert ready_row["avg_latency_ms"] == 2000
    assert ready_row["hit_rate"] == 50.0
    assert ready_row["recent_exception_count"] == 1
    assert ready_row["action_enabled"] is True

    empty_row = next(item for item in payload["items"] if item["id"] == unconfigured_knowledge.id)
    assert empty_row["status"] == "unconfigured"
    assert empty_row["action_enabled"] is False

    items_response = client.get(
        "/api/v1/knowledge/workbench/items?tab=low-hit&keyword=Support&page_size=1",
        headers=_headers(),
    )
    assert items_response.status_code == status.HTTP_200_OK
    items_payload = items_response.json()["data"]
    assert "summary" not in items_payload
    assert items_payload["page_size"] == 1
    assert items_payload["next_page_token"] is None
    assert [item["id"] for item in items_payload["items"]] == [ready_knowledge.id]

    paged_response = client.get("/api/v1/knowledge/workbench/items?page_size=1", headers=_headers())
    assert paged_response.status_code == status.HTTP_200_OK
    assert paged_response.json()["data"]["next_page_token"] is not None


def test_knowledge_crud_and_observe_contract(client):
    create_resp = client.post(
        "/api/v1/knowledge",
        json={
            "name": "knowledge-api-contract",
            "description": "contract",
            "knowledge_type": "code",
            "visibility": "private",
            "tags": ["knowledge"],
        },
        headers=_headers(),
    )
    assert create_resp.status_code == status.HTTP_201_CREATED
    knowledge = create_resp.json()["data"]
    knowledge_id = knowledge["id"]
    assert knowledge["name"] == "knowledge-api-contract"
    assert knowledge["knowledge_type"] == "code"
    assert "source_kind" not in knowledge

    list_resp = client.get("/api/v1/knowledge", headers=_headers())
    assert list_resp.status_code == status.HTTP_200_OK
    assert any(item["id"] == knowledge_id for item in list_resp.json()["data"]["items"])

    detail_resp = client.get(f"/api/v1/knowledge/{knowledge_id}", headers=_headers())
    assert detail_resp.status_code == status.HTTP_200_OK
    detail = detail_resp.json()["data"]
    assert detail["id"] == knowledge_id

    update_resp = client.put(
        f"/api/v1/knowledge/{knowledge_id}",
        json={
            "description": "updated knowledge description",
            "retrieval_json": {"strategy": "hybrid"},
            "tags": ["updated"],
        },
        headers=_headers(),
    )
    assert update_resp.status_code == status.HTTP_200_OK
    updated = update_resp.json()["data"]
    assert updated["description"] == "updated knowledge description"
    assert updated["retrieval_json"]["strategy"] == "hybrid"
    assert updated["tags"] == ["updated"]

    docs_resp = client.get(f"/api/v1/knowledge/{knowledge_id}/documents", headers=_headers())
    assert docs_resp.status_code == status.HTTP_200_OK
    assert docs_resp.json()["data"] == []

    runs_resp = client.get(f"/api/v1/knowledge/{knowledge_id}/runs", headers=_headers())
    assert runs_resp.status_code == status.HTTP_200_OK
    assert isinstance(runs_resp.json()["data"]["items"], list)

    costs_resp = client.get(f"/api/v1/knowledge/{knowledge_id}/runs/costs/summary", headers=_headers())
    assert costs_resp.status_code == status.HTTP_200_OK
    costs = costs_resp.json()["data"]
    assert "tokens_prompt" in costs
    assert "ms_total" in costs

    by_mode_resp = client.get(f"/api/v1/knowledge/{knowledge_id}/runs/costs/by-mode", headers=_headers())
    assert by_mode_resp.status_code == status.HTTP_200_OK
    assert isinstance(by_mode_resp.json()["data"], list)

    usages_resp = client.get(f"/api/v1/knowledge/{knowledge_id}/usages", headers=_headers())
    assert usages_resp.status_code == status.HTTP_200_OK
    assert isinstance(usages_resp.json()["data"], list)

    delete_resp = client.delete(f"/api/v1/knowledge/{knowledge_id}", headers=_headers())
    assert delete_resp.status_code == status.HTTP_204_NO_CONTENT


def test_knowledge_response_does_not_expose_document_source_kind(client):
    create_resp = client.post(
        "/api/v1/knowledge",
        json={
            "name": "knowledge-without-document-source-kind",
            "description": "contract",
            "knowledge_type": "document",
            "visibility": "private",
        },
        headers=_headers(),
    )
    assert create_resp.status_code == status.HTTP_201_CREATED
    knowledge_id = create_resp.json()["data"]["id"]

    list_resp = client.get("/api/v1/knowledge", headers=_headers())
    assert list_resp.status_code == status.HTTP_200_OK
    item = next(entry for entry in list_resp.json()["data"]["items"] if entry["id"] == knowledge_id)
    assert "source_kind" not in item

    detail_resp = client.get(f"/api/v1/knowledge/{knowledge_id}", headers=_headers())
    assert detail_resp.status_code == status.HTTP_200_OK
    assert "source_kind" not in detail_resp.json()["data"]


def test_knowledge_upload_ingest_task_retry_contract(client):
    create_resp = client.post(
        "/api/v1/knowledge",
        json={
            "name": "knowledge-ingest-contract",
            "description": "ingest contract",
            "knowledge_type": "document",
            "visibility": "private",
            "default_embedding_model_ref": "model:test:embedding",
        },
        headers=_headers(),
    )
    assert create_resp.status_code == status.HTTP_201_CREATED
    knowledge_id = create_resp.json()["data"]["id"]

    upload_resp = client.post(
        f"/api/v1/knowledge/{knowledge_id}/documents",
        data={
            "doc_key": "contract-doc",
            "source_kind": "upload",
            "title": "Contract Doc",
            "filename": "contract.txt",
            "mime_type": "text/plain",
            "async_ingest": "true",
            "max_retries": "2",
        },
        files={"file": ("contract.txt", b"Knowledge contract text", "text/plain")},
        headers=_headers(),
    )
    assert upload_resp.status_code == status.HTTP_201_CREATED
    document = upload_resp.json()["data"]
    assert document["status"] == "queued"
    assert document["source_kind"] == "upload"
    assert "source_type" not in document

    tasks_resp = client.get(f"/api/v1/knowledge/{knowledge_id}/ingest-tasks", headers=_headers())
    assert tasks_resp.status_code == status.HTTP_200_OK
    tasks = tasks_resp.json()["data"]
    assert len(tasks) == 1
    task = tasks[0]
    assert task["document_id"] == document["id"]
    assert task["status"] == "queued"
    assert task["max_retries"] == 2
    assert "error_message" in task
    assert "run_id" in task

    cancel_resp = client.post(f"/api/v1/knowledge/{knowledge_id}/ingest-tasks/{task['id']}/cancel", headers=_headers())
    assert cancel_resp.status_code == status.HTTP_200_OK
    assert cancel_resp.json()["data"]["status"] == "canceled"

    retry_resp = client.post(f"/api/v1/knowledge/{knowledge_id}/ingest-tasks/{task['id']}/retry", headers=_headers())
    assert retry_resp.status_code == status.HTTP_200_OK
    retried = retry_resp.json()["data"]
    assert retried["status"] == "queued"
    assert retried["error_code"] is None
    assert retried["error_message"] is None


def test_knowledge_index_rebuild_returns_observable_run_fields(client):
    create_resp = client.post(
        "/api/v1/knowledge",
        json={
            "name": "knowledge-index-observe-contract",
            "description": "index observe contract",
            "knowledge_type": "document",
            "visibility": "private",
        },
        headers=_headers(),
    )
    assert create_resp.status_code == status.HTTP_201_CREATED
    knowledge_id = create_resp.json()["data"]["id"]

    create_index_resp = client.post(
        f"/api/v1/knowledge/{knowledge_id}/indexes",
        json={
            "name": "primary",
            "provider": "memory",
            "embedding_model_ref": "model:test:embedding",
            "dimension": 3,
            "metric_type": "cosine",
            "is_primary": True,
        },
        headers=_headers(),
    )
    assert create_index_resp.status_code == status.HTTP_201_CREATED
    created_index = create_index_resp.json()["data"]
    assert "last_run_id" in created_index
    assert "last_build_at" in created_index
    assert "last_error_code" in created_index
    assert "last_error_message" in created_index

    rebuild_resp = client.post(
        f"/api/v1/knowledge/{knowledge_id}/indexes/{created_index['id']}/rebuild",
        headers=_headers(),
    )
    assert rebuild_resp.status_code == status.HTTP_200_OK
    rebuilt = rebuild_resp.json()["data"]
    assert rebuilt["status"] == "ready"
    assert rebuilt["last_run_id"]
    assert rebuilt["last_build_at"] is not None
    assert rebuilt["last_error_code"] is None
    assert rebuilt["last_error_message"] is None


def test_knowledge_upload_rejects_legacy_source_type(client):
    create_resp = client.post(
        "/api/v1/knowledge",
        json={
            "name": "knowledge-source-kind-contract",
            "description": "source kind contract",
            "knowledge_type": "document",
            "visibility": "private",
            "default_embedding_model_ref": "model:test:embedding",
        },
        headers=_headers(),
    )
    assert create_resp.status_code == status.HTTP_201_CREATED
    knowledge_id = create_resp.json()["data"]["id"]

    upload_resp = client.post(
        f"/api/v1/knowledge/{knowledge_id}/documents",
        data={
            "doc_key": "legacy-source-type-doc",
            "source_type": "upload",
            "title": "Legacy Source Type Doc",
            "filename": "legacy.txt",
            "mime_type": "text/plain",
            "async_ingest": "true",
        },
        files={"file": ("legacy.txt", b"Legacy source type text", "text/plain")},
        headers=_headers(),
    )
    assert upload_resp.status_code == status.HTTP_400_BAD_REQUEST
