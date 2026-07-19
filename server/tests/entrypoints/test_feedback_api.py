"""Entrypoint tests for workspace-local product feedback."""

from contextlib import contextmanager

from fastapi import status

from app.kernel.contracts.context import RequestContext
from app.main import app
from app.middleware.auth import get_current_context


@contextmanager
def _as_context(ctx: RequestContext):
    previous = app.dependency_overrides.get(get_current_context)

    async def _override() -> RequestContext:
        return ctx

    app.dependency_overrides[get_current_context] = _override
    try:
        yield
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_current_context, None)
        else:
            app.dependency_overrides[get_current_context] = previous


def _create_payload(title: str) -> dict[str, object]:
    return {
        "title": title,
        "description": "The behavior is reproducible in the current workspace.",
        "category": "bug",
        "priority": "high",
        "context": {"page_path": "/workflow/wf_123/build"},
    }


def test_workspace_member_can_submit_product_feedback(client) -> None:
    response = client.post(
        "/api/v1/feedback",
        json={
            "title": "Workflow editor loses unsaved changes",
            "description": "Switching tabs discards the current node configuration.",
            "category": "bug",
            "priority": "high",
            "context": {
                "page_path": "/workflow/wf_123/build",
                "app_version": "0.2.0",
                "browser": "Chromium",
                "os": "Windows",
            },
        },
    )

    assert response.status_code == status.HTTP_201_CREATED
    payload = response.json()["data"]
    assert payload["title"] == "Workflow editor loses unsaved changes"
    assert payload["status"] == "open"
    assert payload["created_by"] == "test-user"
    assert payload["tenant_id"] == "test-tenant"
    assert payload["workspace_id"] == "test-workspace"


def test_feedback_list_is_creator_scoped_until_owner_requests_workspace(client) -> None:
    owner_feedback = client.post(
        "/api/v1/feedback",
        json=_create_payload("Owner issue"),
    ).json()["data"]
    viewer = RequestContext(
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        user_id="viewer-user",
        workspace_role="Viewer",
        tenant_role="Viewer",
    )

    with _as_context(viewer):
        viewer_response = client.post(
            "/api/v1/feedback",
            json=_create_payload("Viewer issue"),
        )
        assert viewer_response.status_code == status.HTTP_201_CREATED
        viewer_feedback = viewer_response.json()["data"]

        mine_response = client.get("/api/v1/feedback")
        assert mine_response.status_code == status.HTTP_200_OK
        assert [item["id"] for item in mine_response.json()["data"]["items"]] == [
            viewer_feedback["id"]
        ]

        workspace_response = client.get("/api/v1/feedback", params={"scope": "workspace"})
        assert workspace_response.status_code == status.HTTP_403_FORBIDDEN

    owner_workspace_response = client.get(
        "/api/v1/feedback",
        params={"scope": "workspace"},
    )
    assert owner_workspace_response.status_code == status.HTTP_200_OK
    assert {item["id"] for item in owner_workspace_response.json()["data"]["items"]} == {
        owner_feedback["id"],
        viewer_feedback["id"],
    }


def test_owner_resolves_feedback_and_creator_can_read_the_result(client) -> None:
    viewer = RequestContext(
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        user_id="viewer-user",
        workspace_role="Viewer",
        tenant_role="Viewer",
    )
    with _as_context(viewer):
        created = client.post(
            "/api/v1/feedback",
            json=_create_payload("Viewer issue"),
        ).json()["data"]

    missing_note = client.patch(
        f"/api/v1/feedback/{created['id']}",
        json={"status": "resolved"},
    )
    assert missing_note.status_code == status.HTTP_400_BAD_REQUEST

    resolved = client.patch(
        f"/api/v1/feedback/{created['id']}",
        json={
            "status": "resolved",
            "priority": "critical",
            "resolution_note": "Fixed in the workflow editor.",
        },
    )
    assert resolved.status_code == status.HTTP_200_OK
    assert resolved.json()["data"]["status"] == "resolved"
    assert resolved.json()["data"]["resolved_by"] == "test-user"

    with _as_context(viewer):
        detail = client.get(f"/api/v1/feedback/{created['id']}")
        assert detail.status_code == status.HTTP_200_OK
        assert detail.json()["data"]["resolution_note"] == "Fixed in the workflow editor."


def test_feedback_filters_and_summary_use_the_requested_scope(client) -> None:
    first = client.post(
        "/api/v1/feedback",
        json=_create_payload("Workflow owner issue"),
    ).json()["data"]
    client.post(
        "/api/v1/feedback",
        json={
            **_create_payload("Feature request"),
            "category": "feature",
            "priority": "low",
        },
    )
    client.patch(
        f"/api/v1/feedback/{first['id']}",
        json={"status": "resolved", "resolution_note": "Released."},
    )

    filtered = client.get(
        "/api/v1/feedback",
        params={
            "scope": "workspace",
            "status": "resolved",
            "category": "bug",
            "priority": "high",
            "q": "owner",
        },
    )
    assert filtered.status_code == status.HTTP_200_OK
    assert [item["id"] for item in filtered.json()["data"]["items"]] == [first["id"]]

    summary = client.get("/api/v1/feedback/summary", params={"scope": "workspace"})
    assert summary.status_code == status.HTTP_200_OK
    assert summary.json()["data"] == {
        "total": 2,
        "by_status": {"open": 1, "in_progress": 0, "resolved": 1, "closed": 0},
        "by_category": {
            "bug": 1,
            "feature": 1,
            "performance": 0,
            "usability": 0,
            "other": 0,
        },
        "by_priority": {"low": 1, "medium": 0, "high": 1, "critical": 0},
    }


def test_feedback_from_another_workspace_is_not_visible(client, db) -> None:
    from app.modules.feedback.domain.models import ProductFeedback

    outside = ProductFeedback(
        id="fbk_outside_workspace",
        tenant_id="test-tenant",
        workspace_id="other-workspace",
        title="Outside issue",
        description="This record belongs to another workspace.",
        category="bug",
        priority="high",
        status="open",
        created_by="test-user",
        updated_by="test-user",
    )
    db.add(outside)
    db.commit()

    detail = client.get(f"/api/v1/feedback/{outside.id}")
    assert detail.status_code == status.HTTP_404_NOT_FOUND
    workspace_items = client.get(
        "/api/v1/feedback",
        params={"scope": "workspace"},
    ).json()["data"]["items"]
    assert outside.id not in {item["id"] for item in workspace_items}
