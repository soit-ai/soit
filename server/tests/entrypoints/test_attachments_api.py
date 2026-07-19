"""Entry-point contracts for governed chat attachments."""

from dataclasses import replace

from fastapi import status

from app.main import app
from app.middleware.auth import get_current_context


def test_attachment_upload_download_and_workspace_scope(client, ctx):
    headers = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}
    uploaded = client.post(
        "/api/v1/attachments",
        files={"file": ("support-notes.txt", b"refund policy", "text/plain")},
        headers=headers,
    )

    assert uploaded.status_code == status.HTTP_201_CREATED
    attachment = uploaded.json()["data"]
    assert attachment["id"].startswith("att_")
    assert attachment["filename"] == "support-notes.txt"
    assert attachment["content_type"] == "text/plain"
    assert attachment["size_bytes"] == len(b"refund policy")
    assert attachment["status"] == "ready"
    assert attachment["checksum"].startswith("sha256:")
    assert "storage_key" not in attachment

    downloaded = client.get(
        f"/api/v1/attachments/{attachment['id']}/content",
        headers=headers,
    )
    assert downloaded.status_code == status.HTTP_200_OK
    assert downloaded.content == b"refund policy"
    assert downloaded.headers["content-type"].startswith("text/plain")
    assert downloaded.headers["content-disposition"].startswith("attachment;")
    assert downloaded.headers["content-security-policy"] == "sandbox; default-src 'none'"

    original_context_override = app.dependency_overrides[get_current_context]

    async def _other_workspace_context():
        return replace(ctx, workspace_id="other-workspace")

    app.dependency_overrides[get_current_context] = _other_workspace_context
    try:
        wrong_workspace = client.get(f"/api/v1/attachments/{attachment['id']}")
    finally:
        app.dependency_overrides[get_current_context] = original_context_override
    assert wrong_workspace.status_code == status.HTTP_404_NOT_FOUND


def test_attachment_upload_rejects_executable_content(client):
    response = client.post(
        "/api/v1/attachments",
        files={"file": ("payload.exe", b"MZ-not-allowed", "application/octet-stream")},
        headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["code"] == "VALIDATION_ERROR"
