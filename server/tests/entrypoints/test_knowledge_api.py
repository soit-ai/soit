"""Entrypoint tests for the knowledge API contract."""

from fastapi import status


def _headers() -> dict:
    return {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}


def test_knowledge_crud_and_observability_contract(client):
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
    assert knowledge["source_type"] == "code"

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

    legacy_usages_resp = client.get(f"/api/v1/knowledge/{knowledge_id}/applications", headers=_headers())
    assert legacy_usages_resp.status_code == status.HTTP_404_NOT_FOUND

    delete_resp = client.delete(f"/api/v1/knowledge/{knowledge_id}", headers=_headers())
    assert delete_resp.status_code == status.HTTP_204_NO_CONTENT
